"""Independent review of Phase 3 (vendors, P&L, balance sheet). Each test here FAILS on the code as
reviewed and shows one bug. Own data, own schema reset (same pattern as test_books_api.py).
Skipped unless TEST_DATABASE_URL points at an empty test database."""

import os

import pytest

TEST_DB = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DB, reason="set TEST_DATABASE_URL to run")

OWNER = {"X-Dev-Email": "owner@example.com"}
EMP = {"X-Dev-Email": "revemp@example.com"}


@pytest.fixture(scope="module")
def client():
    os.environ.update(DATABASE_URL=TEST_DB, AUTH_MODE="dev", BOOTSTRAP_OWNER_EMAIL="owner@example.com", ADMIN_EMAILS="admin@example.com")
    import psycopg

    with psycopg.connect(TEST_DB, autocommit=True) as conn:
        conn.execute("drop schema public cascade; create schema public;")
    from scripts import migrate

    migrate.main()
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture(scope="module")
def world(client):
    a = client.post("/api/stores", json={"name": "Rev A"}, headers=OWNER).json()
    b = client.post("/api/stores", json={"name": "Rev B"}, headers=OWNER).json()
    client.post("/api/people", json={"email": "revemp@example.com", "name": "Rae", "store_ids": [a["id"], b["id"]]}, headers=OWNER)

    def day(store, d, fuel, merch, tax, drop, paid_outs):
        r = client.put("/api/reports", json={"store_id": store["id"], "business_date": d, "fuel_sale": fuel, "merch_sale": merch,
                                              "sales_tax": tax, "cash_drop": drop, "paid_outs": paid_outs}, headers=EMP)
        assert r.status_code == 200, r.text
        client.post(f"/api/reports/{r.json()['id']}/submit", headers=EMP)
        assert client.post(f"/api/reports/{r.json()['id']}/approve", json={}, headers=OWNER).status_code == 200

    # Store A, Oct 1: 1000 sales, a 100.00 cash paid out to "Rent Co" (an expense vendor), drop 900 → balanced day
    client.post("/api/vendors", json={"name": "Rent Co", "kind": "expense"}, headers=OWNER)
    day(a, "2026-10-01", "1000.00", "0", "0", "900.00", [{"kind": "cash", "payee": "Rent Co", "amount": "100.00"}])
    # Store B, Oct 1: 500 sales, no paid outs
    day(b, "2026-10-01", "500.00", "0", "0", "500.00", [])
    return {"a": a, "b": b}


def _owner_conn_and_user():
    import psycopg
    from psycopg.rows import dict_row

    from app.core.auth import CurrentUser

    c1 = psycopg.connect(TEST_DB, row_factory=dict_row)
    c2 = psycopg.connect(TEST_DB, row_factory=dict_row)
    o = c1.execute("select id, email, name, role from people where email = 'owner@example.com'").fetchone()
    c1.commit()
    return c1, c2, CurrentUser(id=o["id"], email=o["email"], name=o["name"], role=o["role"])


# ---------------------------------------------------------------- validation → 500

@pytest.mark.parametrize("path", [
    "/api/books/pnl?month=0000-01",
    "/api/books/balance?month=0000-01",
    "/api/books/entries?month=0000-01",
    "/api/books/pnl-year?year=0000",
    "/api/vendors/spending?period=month&value=0000-01",
    "/api/vendors/spending?period=year&value=0000",
])
def test_year_zero_is_a_400_not_a_500(client, world, path):
    # check_month / period_range accept \d{4}, then date(0, 1, 1) raises ValueError → 500
    assert client.get(path, headers=OWNER).status_code in (400, 422), path


def test_entry_for_year_zero_is_rejected_not_500(client, world):
    r = client.post("/api/books/entries", json={"month": "0000-01", "category": "expense", "description": "x", "amount": "1.00"},
                    headers=OWNER)
    assert r.status_code in (400, 422), r.text            # postgres refuses year 0 → DataError → 500


def test_year_9999_overview_is_not_a_500(client, world):
    # _months() steps past Dec 9999 → OverflowError
    assert client.get("/api/books/pnl-year?year=9999", headers=OWNER).status_code in (200, 400)


# ---------------------------------------------------------------- balance sheet

def test_balance_line_name_of_only_spaces_is_rejected(client, world):
    r = client.put("/api/books/balance", json={"month": "2027-03", "lines": [{"section": "asset", "name": "   ", "amount": "5.00"}]},
                   headers=OWNER)
    assert r.status_code == 422, r.json().get("typed_lines")   # saved today as a line with an empty name ""


def _second_request_waits(first_call, second_call):
    """Run first_call in connection 1 (not committed yet) and second_call in connection 2 on another thread.
    The second must WAIT for the first to finish (the month lock), then run on top of its result."""
    import threading

    c1, c2, owner = _owner_conn_and_user()
    outcome = {}

    def second():
        try:
            second_call(c2, owner)
            c2.commit()
            outcome["ok"] = True
        except Exception as e:  # noqa: BLE001 - the test inspects what happened
            c2.rollback()
            outcome["error"] = e

    try:
        first_call(c1, owner)
        t = threading.Thread(target=second)
        t.start()
        t.join(timeout=1.0)
        assert t.is_alive(), "the second request didn't wait for the first one"
        c1.commit()
        t.join(timeout=10)
        assert not t.is_alive()
    finally:
        c1.close()
        c2.close()
    return outcome


def test_copy_previous_double_tap_does_not_duplicate_lines(client, world):
    """Two copy-previous requests at the same time (double tap on a phone): the second waits, then finds the month
    already filled and is refused, so every asset is counted once."""
    from app.modules.books import service

    a = world["a"]["id"]
    lines = [{"section": "asset", "name": "Cash in bank", "amount": "1000.00"}]
    assert client.put("/api/books/balance", json={"month": "2026-06", "store_id": a, "lines": lines}, headers=OWNER).status_code == 200
    outcome = _second_request_waits(lambda c, o: service.copy_previous(c, o, "2026-07", a),
                                     lambda c, o: service.copy_previous(c, o, "2026-07", a))
    assert getattr(outcome.get("error"), "status_code", None) == 409
    sheet = client.get(f"/api/books/balance?month=2026-07&store_id={a}", headers=OWNER).json()
    assert sheet["total_assets"] == "1000.00", sheet["typed_lines"]


def test_two_saves_of_an_empty_month_do_not_double_the_lines(client, world):
    """Same on PUT /balance (a double-click on Save): the second save waits and replaces, it doesn't add."""
    from app.modules.books import service
    from app.modules.books.schemas import BalanceIn

    b = world["b"]["id"]
    data = BalanceIn(month="2026-08", store_id=b, lines=[{"section": "asset", "name": "Cash on hand", "amount": "250.00"}])
    outcome = _second_request_waits(lambda c, o: service.save_balance(c, o, data), lambda c, o: service.save_balance(c, o, data))
    assert outcome.get("ok")
    sheet = client.get(f"/api/books/balance?month=2026-08&store_id={b}", headers=OWNER).json()
    assert sheet["total_assets"] == "250.00", sheet["typed_lines"]


def test_all_stores_balance_sheet_includes_each_stores_typed_lines(client, world):
    """'All stores' equity includes every store's profit to date (and every store's tax), but its assets are only the
    SHARED lines: a store's bank balance typed on its own sheet never reaches the All-stores sheet, so the group
    sheet is off by every store's assets. Spec: 'All stores shows everything'."""
    a = world["a"]["id"]
    lines = [{"section": "asset", "name": "Store A bank", "amount": "800.00"}]
    assert client.put("/api/books/balance", json={"month": "2026-10", "store_id": a, "lines": lines}, headers=OWNER).status_code == 200
    group = client.get("/api/books/balance?month=2026-10", headers=OWNER).json()
    assert any(l["label"].startswith("Store A bank (") for l in group["assets"]), group["assets"]
    assert group["typed_lines"] == []          # the group view edits only the shared lines; each store edits its own


def test_balance_profit_to_date_can_follow_the_paid_out_toggle(client, world):
    """P&L lets the owner turn off paid outs when the same payments are typed in (so nothing counts twice), but
    profit_to_date always uses count_paid_outs=True, so the balance sheet double counts them anyway."""
    a = world["a"]["id"]
    client.post("/api/books/entries", json={"month": "2026-10", "store_id": a, "category": "expense",
                                             "description": "Rent (also paid from the drawer)", "amount": "100.00"}, headers=OWNER)
    pnl_off = client.get(f"/api/books/pnl?month=2026-10&store_id={a}&count_paid_outs=false", headers=OWNER).json()
    sheet = client.get(f"/api/books/balance?month=2026-10&store_id={a}&count_paid_outs=false", headers=OWNER).json()
    assert sheet["equity"][-1]["amount"] == pnl_off["net_profit"]          # 900.00 vs 800.00 today


# ---------------------------------------------------------------- vendors

def test_typed_entry_cannot_use_a_deactivated_vendor(client, world):
    v = client.post("/api/vendors", json={"name": "Old Supplier", "kind": "merchandise", "active": False}, headers=OWNER).json()
    r = client.post("/api/books/entries", json={"month": "2026-10", "category": "merchandise_purchase", "description": "x",
                                                 "amount": "1.00", "vendor_id": v["id"]}, headers=OWNER)
    assert r.status_code == 400, r.text
