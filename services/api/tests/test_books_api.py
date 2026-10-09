"""Vendors, Profit & Loss and Balance Sheet through the API, against a real database.
A small worked example: store A (Oct 2026) with paid outs, typed purchases / expenses, and store B.
Skipped unless TEST_DATABASE_URL points at an empty test database."""

import os
from decimal import Decimal as D

import pytest

TEST_DB = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DB, reason="set TEST_DATABASE_URL to run")

OWNER = {"X-Dev-Email": "owner@example.com"}
ADMIN = {"X-Dev-Email": "admin@example.com"}
EMP = {"X-Dev-Email": "bookemp@example.com"}


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
    """Stores A and B, an employee at A, three vendors, worksheets and typed entries for Oct 2026."""
    a = client.post("/api/stores", json={"name": "Store A"}, headers=OWNER).json()
    b = client.post("/api/stores", json={"name": "Store B"}, headers=OWNER).json()
    client.post("/api/people", json={"email": "bookemp@example.com", "name": "Bea", "store_ids": [a["id"], b["id"]]}, headers=OWNER)

    def day(store, d, fuel, merch, tax, drop, paid_outs, approve=True):
        r = client.put("/api/reports", json={"store_id": store["id"], "business_date": d, "fuel_sale": fuel, "merch_sale": merch,
                                              "sales_tax": tax, "cash_drop": drop, "paid_outs": paid_outs}, headers=EMP)
        assert r.status_code == 200, r.text
        client.post(f"/api/reports/{r.json()['id']}/submit", headers=EMP)
        if approve:
            assert client.post(f"/api/reports/{r.json()['id']}/approve", json={}, headers=OWNER).status_code == 200

    # Store A, Oct 1: sales 1,509 (incl. 9 tax). Cash paid out 60 (Pepsi 50, Bob's 10); Ice Co by check. Drop 1,444 → short 5.00
    day(a, "2026-10-01", "1000.00", "500.00", "9.00", "1444.00", [
        {"kind": "cash", "payee": "pepsi ", "amount": "50.00"},
        {"kind": "check", "check_no": "77", "payee": "Ice Co", "amount": "20.00"},
        {"kind": "cash", "payee": "Bob's Repair", "amount": "10.00"}])
    day(a, "2026-10-02", "100.00", "0", "0", "100.00", [], approve=False)          # waiting for review
    day(b, "2026-10-01", "300.00", "100.00", "0", "400.00", [])                     # Store B

    # Vendors added after those days were submitted (since Oct 9, submit needs listed names; old days keep theirs)
    v = {name: client.post("/api/vendors", json={"name": name, "kind": kind}, headers=OWNER).json()
         for name, kind in [("Sunoco Fuel", "fuel"), ("Pepsi", "merchandise"), ("Ice Co", "expense")]}

    def entry(store, month, category, description, amount, vendor=None):
        r = client.post("/api/books/entries", json={"month": month, "store_id": store and store["id"], "category": category,
                                                     "description": description, "amount": amount,
                                                     "vendor_id": vendor and v[vendor]["id"]}, headers=OWNER)
        assert r.status_code == 200, r.text
        return r.json()

    entry(a, "2026-10", "fuel_purchase", "Load Oct 3", "700.00", "Sunoco Fuel")
    entry(a, "2026-10", "expense", "Payroll", "200.00")
    entry(None, "2026-10", "expense", "Insurance", "100.00")                        # shared by all stores
    entry(a, "2026-09", "expense", "Permit", "15.00")                               # earlier month, for profit to date
    return {"a": a, "b": b, "v": v}


def test_profit_and_loss_for_one_store_matches_hand_math(client, world):
    p = client.get(f"/api/books/pnl?month=2026-10&store_id={world['a']['id']}", headers=OWNER).json()
    assert (p["revenue"], p["cost_of_goods"], p["gross_profit"], p["expenses"], p["over_short"], p["net_profit"]) == \
           ("1500.00", "750.00", "750.00", "230.00", "-5.00", "515.00")
    assert p["sales_tax"] == "9.00" and p["days"] == 1
    assert [(l["label"], l["amount"]) for l in p["cost_lines"]] == [("Fuel purchases", "700.00"), ("Paid outs: merchandise vendors", "50.00")]
    assert [(l["label"], l["amount"]) for l in p["expense_lines"]] == [
        ("Payroll", "200.00"), ("Paid outs: Ice Co", "20.00"), ("Paid outs: vendors not on the list", "10.00")]
    assert isinstance(p["net_profit"], str)                                         # exact money, never a float


def test_all_stores_include_shared_entries_and_other_stores(client, world):
    p = client.get("/api/books/pnl?month=2026-10", headers=OWNER).json()
    assert (p["revenue"], p["cost_of_goods"], p["expenses"], p["net_profit"]) == ("1900.00", "750.00", "330.00", "815.00")


def test_paid_outs_toggle_and_waiting_days(client, world):
    q = f"month=2026-10&store_id={world['a']['id']}"
    off = client.get(f"/api/books/pnl?{q}&count_paid_outs=false", headers=OWNER).json()
    assert (off["cost_of_goods"], off["expenses"], off["net_profit"]) == ("700.00", "200.00", "595.00")
    more = client.get(f"/api/books/pnl?{q}&include=submitted", headers=OWNER).json()
    assert more["revenue"] == "1600.00" and more["days"] == 2


def test_year_view_adds_up_the_months(client, world):
    y = client.get(f"/api/books/pnl-year?year=2026&store_id={world['a']['id']}", headers=OWNER).json()
    by_month = {m["month"]: m for m in y["months"]}
    assert len(y["months"]) == 12 and by_month["2026-10"]["net_profit"] == "515.00" and by_month["2026-09"]["net_profit"] == "-15.00"
    assert y["totals"]["net_profit"] == "500.00"


def test_balance_sheet_check_profit_to_date_and_tax(client, world):
    a = world["a"]["id"]
    lines = [{"section": "asset", "name": "Cash in bank", "amount": "10000.00"},
             {"section": "liability", "name": "Accounts payable", "amount": "2000.00"},
             {"section": "equity", "name": "Owner's investment", "amount": "7476.00"}]
    r = client.put("/api/books/balance", json={"month": "2026-10", "store_id": a, "lines": lines}, headers=OWNER)
    assert r.status_code == 200, r.text
    b = r.json()
    assert (b["total_assets"], b["total_liabilities"], b["total_equity"]) == ("10000.00", "2009.00", "7976.00")
    assert b["liabilities"][-1]["amount"] == "9.00" and b["equity"][-1]["amount"] == "500.00"   # Sep −15 + Oct 515
    assert b["difference"] == "15.00" and b["balanced"] is False
    fixed = lines[:2] + [{"section": "equity", "name": "Owner's investment", "amount": "7491.00"}]
    assert client.put("/api/books/balance", json={"month": "2026-10", "store_id": a, "lines": fixed}, headers=OWNER).json()["balanced"] is True


def test_copy_previous_never_overwrites(client, world):
    a = world["a"]["id"]
    r = client.post(f"/api/books/balance/copy-previous?month=2026-11&store_id={a}", headers=OWNER)
    assert r.status_code == 200 and r.json()["copied"] == 3
    again = client.post(f"/api/books/balance/copy-previous?month=2026-11&store_id={a}", headers=OWNER)
    assert again.status_code == 409
    assert client.post(f"/api/books/balance/copy-previous?month=2026-01&store_id={a}", headers=OWNER).status_code == 400
    # another store's (or the shared) balances are separate
    assert client.get("/api/books/balance?month=2026-10", headers=OWNER).json()["typed_lines"] == []


def test_entries_edit_delete_and_history(client, world):
    e = client.post("/api/books/entries", json={"month": "2026-12", "category": "expense", "description": "  Snow   removal ",
                                                 "amount": "75.00"}, headers=OWNER).json()
    assert e["description"] == "Snow removal" and e["store_id"] is None
    changed = client.patch(f"/api/books/entries/{e['id']}", json={"month": "2026-12", "category": "expense",
                                                                   "description": "Snow removal", "amount": "80.00"}, headers=OWNER)
    assert changed.json()["amount"] == "80.00"
    assert [x["amount"] for x in client.get("/api/books/entries?month=2026-12", headers=OWNER).json()] == ["80.00"]
    assert client.delete(f"/api/books/entries/{e['id']}", headers=OWNER).json() == {"ok": True}
    assert client.get("/api/books/entries?month=2026-12", headers=OWNER).json() == []
    assert client.delete(f"/api/books/entries/{e['id']}", headers=OWNER).status_code == 404

    import psycopg
    with psycopg.connect(TEST_DB) as conn:
        actions = [r[0] for r in conn.execute("select action from audit_log where details->>'id' = %s order by at", [e["id"]])]
    assert actions == ["ledger.added", "ledger.changed", "ledger.deleted"]          # nothing disappears without a trace


def test_entry_validation(client, world):
    base = {"month": "2026-10", "category": "expense", "description": "X", "amount": "1.00"}
    assert client.post("/api/books/entries", json=base | {"amount": "-1.00"}, headers=OWNER).status_code == 422
    assert client.post("/api/books/entries", json=base | {"month": "2026-13"}, headers=OWNER).status_code == 422
    assert client.post("/api/books/entries", json=base | {"description": "   "}, headers=OWNER).status_code == 422
    assert client.post("/api/books/entries", json=base | {"category": "lunch"}, headers=OWNER).status_code == 422
    bogus = "00000000-0000-0000-0000-000000000000"
    assert client.post("/api/books/entries", json=base | {"vendor_id": bogus}, headers=OWNER).status_code == 400
    assert client.post("/api/books/entries", json=base | {"store_id": bogus}, headers=OWNER).status_code == 400
    assert client.get("/api/books/pnl?month=2026-1", headers=OWNER).status_code == 400


def test_vendors_rules_and_spending(client, world):
    v = world["v"]
    assert client.post("/api/vendors", json={"name": "  PEPSI ", "kind": "expense"}, headers=OWNER).status_code == 409
    assert client.delete(f"/api/vendors/{v['Sunoco Fuel']['id']}", headers=OWNER).status_code == 409   # has a purchase
    gone = client.post("/api/vendors", json={"name": "Temp Vendor", "kind": "expense"}, headers=OWNER).json()
    assert client.delete(f"/api/vendors/{gone['id']}", headers=OWNER).json() == {"ok": True}
    off = client.patch(f"/api/vendors/{v['Ice Co']['id']}", json={"name": "Ice Co", "kind": "expense", "active": False}, headers=OWNER).json()
    assert off["active"] is False
    client.patch(f"/api/vendors/{v['Ice Co']['id']}", json={"name": "Ice Co", "kind": "expense", "active": True}, headers=OWNER)

    s = client.get(f"/api/vendors/spending?period=month&value=2026-10&store_id={world['a']['id']}", headers=OWNER).json()
    rows = {r["vendor"]: r for r in s["vendors"]}
    assert s["total"] == "780.00"
    assert (rows["Sunoco Fuel"]["cost_of_goods"], rows["Pepsi"]["cost_of_goods"], rows["Ice Co"]["expense"], rows["Bob's Repair"]["not_on_list"]) == \
           ("700.00", "50.00", "20.00", "10.00")
    assert rows["Bob's Repair"]["on_list"] is False and rows["Sunoco Fuel"]["share"] == "89.7"
    assert [r["vendor"] for r in s["vendors"]][0] == "Sunoco Fuel"                   # biggest first


def test_store_with_books_cannot_be_deleted(client, world):
    r = client.delete(f"/api/stores/{world['a']['id']}", headers=OWNER)
    assert r.status_code == 409


def test_employees_and_view_as_cannot_touch_the_books(client, world):
    for method, path in [("get", "/api/vendors"), ("get", "/api/books/pnl?month=2026-10"), ("get", "/api/books/balance?month=2026-10"),
                         ("get", "/api/books/entries?month=2026-10"), ("get", "/api/vendors/spending?period=year&value=2026"),
                         ("get", "/api/books/pnl-year?year=2026")]:
        assert getattr(client, method)(path, headers=EMP).status_code == 403, path
    assert client.post("/api/vendors", json={"name": "Sneaky", "kind": "expense"}, headers=EMP).status_code == 403
    assert client.post("/api/books/entries", json={"month": "2026-10", "category": "expense", "description": "x", "amount": "1"},
                       headers=EMP).status_code == 403

    # the app admin "viewing as" the owner can look but not change anything
    me = client.get("/api/me", headers=ADMIN).json()
    owner_id = next(o["id"] for o in me["view_as_options"] if o["role"] == "owner")
    as_owner = ADMIN | {"X-View-As": owner_id}
    assert client.get("/api/books/pnl?month=2026-10", headers=as_owner).status_code == 200
    r = client.post("/api/books/entries", json={"month": "2026-10", "category": "expense", "description": "x", "amount": "1"}, headers=as_owner)
    assert r.status_code == 403 and "read-only" in r.json()["detail"]


def test_reading_reports_changes_nothing(client, world):
    import psycopg

    def snapshot():
        with psycopg.connect(TEST_DB) as conn:
            return [conn.execute(f"select * from {t} order by 1").fetchall() for t in ("daily_reports", "paid_outs", "ledger_entries", "balance_lines", "vendors")]

    before = snapshot()
    for path in ["/api/books/pnl?month=2026-10", "/api/books/pnl-year?year=2026", "/api/books/balance?month=2026-10",
                 "/api/vendors/spending?period=year&value=2026", "/api/summaries?period=quarter&value=2026-Q4"]:
        assert client.get(path, headers=OWNER).status_code == 200, path
    assert snapshot() == before
