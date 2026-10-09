"""Independent review of the Oct 9 change (docs/features/owner-call-oct9.md).
Tests marked "BUG" failed on the code as reviewed and were fixed (Oct 9); all now guard against regressions.
Skipped unless TEST_DATABASE_URL points at a throwaway test database (the schema is dropped)."""

import os

import pytest

TEST_DB = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DB, reason="set TEST_DATABASE_URL to run")

OWNER = {"X-Dev-Email": "owner@example.com"}
ADMIN = {"X-Dev-Email": "admin@example.com"}
CO = {"X-Dev-Email": "co@example.com"}
EMP = {"X-Dev-Email": "emp@example.com"}       # store A only
EMP_B = {"X-Dev-Email": "empb@example.com"}    # store B only


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


def ok(r, code=200):
    assert r.status_code == code, r.text
    return r.json()


@pytest.fixture(scope="module")
def world(client):
    a = ok(client.post("/api/stores", json={"name": "Store A", "tank_specs": [
        {"name": "Tank 1", "grade": "Regular", "capacity": 10000}]}, headers=OWNER))
    b = ok(client.post("/api/stores", json={"name": "Store B", "tank_specs": [
        {"name": "Tank 1", "grade": "Regular", "capacity": 10000}]}, headers=OWNER))
    ok(client.post("/api/people", json={"email": "emp@example.com", "name": "Emma", "store_ids": [a["id"]]}, headers=OWNER))
    ok(client.post("/api/people", json={"email": "empb@example.com", "name": "Ben", "store_ids": [b["id"]]}, headers=OWNER))
    ok(client.post("/api/people", json={"email": "co@example.com", "name": "Cora", "role": "coowner"}, headers=OWNER))
    people = {p["email"]: p for p in ok(client.get("/api/people", headers=OWNER))}
    return {"a": a, "b": b, "people": people}


def day(client, store, d, fuel="100.00", gallons="0", tanks=None, submit=True, approve=False, ret=False, who=EMP):
    r = ok(client.put("/api/reports", json={
        "store_id": store["id"], "business_date": d, "fuel_sale": fuel, "gallons": gallons, "cash_drop": fuel,
        "tank_inventory": [{"tank": k, "gallons": v} for k, v in (tanks or {}).items()]}, headers=who))
    if submit:
        ok(client.post(f"/api/reports/{r['id']}/submit", headers=who))
    if approve:
        ok(client.post(f"/api/reports/{r['id']}/approve", json={}, headers=OWNER))
    if ret:
        ok(client.post(f"/api/reports/{r['id']}/return", json={"note": "redo"}, headers=OWNER))
    return r


# ---------- co-owner (regression guards: all pass) ----------

def test_coowner_cannot_change_other_coowners_or_inactive_owners(client, world):
    a = world["a"]
    co_id = world["people"]["co@example.com"]["id"]
    co2 = ok(client.post("/api/people", json={"email": "co2@example.com", "name": "Cal", "role": "coowner"}, headers=OWNER))
    old = ok(client.post("/api/people", json={"email": "old@example.com", "name": "Old", "role": "owner", "active": False}, headers=OWNER))
    # another co-owner: no demote, no rename, no delete, no deactivate
    assert client.patch(f"/api/people/{co2['id']}", json={"email": "co2@example.com", "role": "employee", "store_ids": [a["id"]]}, headers=CO).status_code == 403
    assert client.patch(f"/api/people/{co2['id']}", json={"email": "co2@example.com", "name": "X", "role": "coowner"}, headers=CO).status_code == 403
    assert client.patch(f"/api/people/{co2['id']}", json={"email": "co2@example.com", "role": "coowner", "active": False}, headers=CO).status_code == 403
    assert client.delete(f"/api/people/{co2['id']}", headers=CO).status_code == 403
    # a deactivated owner can't be brought back (or turned into staff) by a co-owner
    assert client.patch(f"/api/people/{old['id']}", json={"email": "old@example.com", "role": "owner", "active": True}, headers=CO).status_code == 403
    assert client.patch(f"/api/people/{old['id']}", json={"email": "old@example.com", "role": "manager", "store_ids": [a["id"]]}, headers=CO).status_code == 403
    # co-owner can't drop or delete their own access
    assert client.patch(f"/api/people/{co_id}", json={"email": "co@example.com", "role": "coowner", "active": False}, headers=CO).status_code == 400
    assert client.patch(f"/api/people/{co_id}", json={"email": "co@example.com", "role": "manager", "store_ids": [a["id"]]}, headers=CO).status_code == 400
    assert client.delete(f"/api/people/{co_id}", headers=CO).status_code == 400
    # taking the owner's email (any case) is refused, not a 500
    emp_id = world["people"]["emp@example.com"]["id"]
    assert client.patch(f"/api/people/{emp_id}", json={"email": "OWNER@example.com", "role": "employee", "store_ids": [a["id"]]}, headers=CO).status_code == 409
    # view-as co-owner stays read-only
    view = {**ADMIN, "X-View-As": str(co_id)}
    assert client.patch(f"/api/people/{emp_id}", json={"email": "emp@example.com", "role": "employee", "store_ids": [a["id"]]}, headers=view).status_code == 403


# ---------- My days history ----------

def test_history_store_isolation(client, world):
    a, b = world["a"], world["b"]
    day(client, a, "2026-06-10", who=EMP)
    day(client, b, "2026-06-11", fuel="555.00", who=EMP_B)
    # employee asks for the other store explicitly: nothing, not even month totals or a next page
    h = ok(client.get(f"/api/reports/history?until=2026-06-30&store_id={b['id']}", headers=EMP))
    assert h == {"days": [], "months": [], "next_until": None}
    h = ok(client.get("/api/reports/history?until=2026-06-30", headers=EMP))
    assert {d["store_id"] for d in h["days"]} == {a["id"]}
    assert {m["store_id"] for m in h["months"]} == {a["id"]}


def test_history_far_past_until_is_not_500(client, world):
    """BUG: until - days (or the day before the page) underflows date.min -> OverflowError -> HTTP 500."""
    for q in ["until=0001-01-10&days=30", "until=0001-01-01&days=1"]:
        r = client.get(f"/api/reports/history?{q}", headers=EMP)
        assert r.status_code < 500, (q, r.status_code, r.text)


def test_history_owner_page_is_not_silently_truncated(client, world):
    """BUG (low): history() caps the page at 1000 rows; an owner with 12 stores x 92 days gets a silently
    short page, and next_until then skips the rows that were cut off."""
    import psycopg

    with psycopg.connect(TEST_DB, autocommit=True) as conn:
        ids = [conn.execute("insert into stores (name) values (%s) returning id", [f"Bulk {i:02}"]).fetchone()[0] for i in range(12)]
        for sid in ids:
            conn.execute("""insert into daily_reports (store_id, business_date, status)
                            select %s, d::date, 'submitted' from generate_series('2025-01-01'::date, '2025-04-02'::date, '1 day') d""", [sid])
        conn.execute("update stores set active = false where name like 'Bulk %%'")
    try:
        h = ok(client.get("/api/reports/history?until=2025-04-02&days=92", headers=OWNER))
        assert len(h["days"]) == 12 * 92
    finally:
        with psycopg.connect(TEST_DB, autocommit=True) as conn:
            conn.execute("delete from daily_reports where store_id = any(%s)", [ids])
            conn.execute("delete from stores where id = any(%s)", [ids])


# ---------- deliveries (books entries) ----------

def test_patch_delivery_only_gallons_keeps_date_and_tank(client, world):
    """BUG (spec mismatch): spec says PATCH keeps entry_date / tank / gallons 'when not sent', but sending only
    `gallons` (to fix the gallons) fails model validation (422) because the validator demands date + tank too,
    before update_entry gets to merge the kept values."""
    a = world["a"]
    d = ok(client.post("/api/books/entries", json={
        "store_id": a["id"], "category": "fuel_purchase", "description": "Load", "amount": "0",
        "entry_date": "2026-09-02", "tank": "Tank 1", "gallons": "4000"}, headers=OWNER))
    r = client.patch(f"/api/books/entries/{d['id']}", json={
        "month": "2026-09", "store_id": a["id"], "category": "fuel_purchase", "description": "Load",
        "amount": "0", "gallons": "4100"}, headers=OWNER)
    e = ok(r)
    assert (e["gallons"], e["tank"], e["entry_date"]) == ("4100.0", "Tank 1", "2026-09-02")


def test_delivery_rules_never_500(client, world):
    a = world["a"]
    base = {"store_id": a["id"], "category": "fuel_purchase", "description": "Load", "amount": "1.00",
            "entry_date": "2026-09-05", "tank": "Tank 1", "gallons": "10"}
    d = ok(client.post("/api/books/entries", json=base, headers=OWNER))
    bad = [
        base | {"gallons": "123456789012.0"},          # too many digits
        base | {"gallons": "1.25"},                     # 2 decimals
        base | {"tank": "x" * 61},
        base | {"entry_date": "2100-01-01"},
        base | {"month": "2026-9"},
    ]
    for body in bad:
        assert client.post("/api/books/entries", json=body, headers=OWNER).status_code in (400, 422), body
        assert client.patch(f"/api/books/entries/{d['id']}", json=body, headers=OWNER).status_code in (400, 422), body
    # clearing the delivery fields explicitly turns it back into a plain fuel purchase
    e = ok(client.patch(f"/api/books/entries/{d['id']}", json=base | {"tank": None, "gallons": None, "entry_date": None, "month": "2026-09"}, headers=OWNER))
    assert (e["tank"], e["gallons"], e["entry_date"]) == (None, None, None)


# ---------- Inventory ----------

def test_inventory_ignores_returned_days_and_other_stores(client, world):
    a, b = world["a"], world["b"]
    day(client, a, "2026-07-31", tanks={"Tank 1": "5000"}, approve=True)
    day(client, a, "2026-08-02", tanks={"Tank 1": "4000"}, approve=True)
    day(client, a, "2026-08-03", tanks={"Tank 1": "100"}, ret=True)          # sent back: not a reading
    day(client, b, "2026-08-03", tanks={"Tank 1": "9999"}, who=EMP_B)        # other store
    ok(client.post("/api/books/entries", json={"store_id": b["id"], "category": "fuel_purchase", "description": "B load",
                                               "amount": "0", "entry_date": "2026-08-02", "tank": "Tank 1", "gallons": "500"}, headers=OWNER))
    t = ok(client.get(f"/api/inventory?month=2026-08&store_id={a['id']}", headers=CO))["stores"][0]["fuel"]["tanks"][0]
    assert (t["latest"], t["latest_day"], t["used"], t["delivered"], t["opening_day"]) == ("4000.0", "2026-08-02", "1000.0", "0.0", "2026-07-31")


def test_inventory_keeps_history_after_tank_rename(client, world):
    """BUG (medium): readings and deliveries are matched to tanks by NAME only. Renaming a tank in Settings
    (e.g. 'Tank 1' -> 'Tank 1 - Regular 87') drops every past reading and delivery from Inventory: latest, used,
    % full and the pump check all go blank, although Settings says 'Past days keep the tank names'."""
    c = ok(client.post("/api/stores", json={"name": "Store C", "tank_specs": [{"name": "Tank 1", "capacity": 10000}]}, headers=OWNER))
    day(client, c, "2026-05-01", tanks={"Tank 1": "6000"}, approve=True, who=OWNER)
    day(client, c, "2026-05-02", tanks={"Tank 1": "5000"}, approve=True, who=OWNER)
    ok(client.patch(f"/api/stores/{c['id']}", json={"name": "Store C", "tank_specs": [{"name": "Tank 1 - Regular 87", "previous_name": "Tank 1", "capacity": 10000}]}, headers=OWNER))
    t = ok(client.get(f"/api/inventory?month=2026-05&store_id={c['id']}", headers=OWNER))["stores"][0]["fuel"]["tanks"][0]
    assert t["latest"] == "5000.0" and t["used"] == "1000.0", t
    # renamed twice: still finds the history; Settings shows the old names
    ok(client.patch(f"/api/stores/{c['id']}", json={"name": "Store C", "tank_specs": [{"name": "Regular", "previous_name": "Tank 1 - Regular 87", "capacity": 10000}]}, headers=OWNER))
    t = ok(client.get(f"/api/inventory?month=2026-05&store_id={c['id']}", headers=OWNER))["stores"][0]["fuel"]["tanks"][0]
    assert t["name"] == "Regular" and t["used"] == "1000.0"
    store = next(s for s in ok(client.get("/api/stores", headers=OWNER)) if s["id"] == c["id"])
    assert store["tank_specs"][0]["aliases"] == ["Tank 1", "Tank 1 - Regular 87"]
    # saving the store again without previous_name keeps the old names
    ok(client.patch(f"/api/stores/{c['id']}", json={"name": "Store C", "tank_specs": store["tank_specs"]}, headers=OWNER))
    assert next(s for s in ok(client.get("/api/stores", headers=OWNER)) if s["id"] == c["id"])["tank_specs"][0]["aliases"] == ["Tank 1", "Tank 1 - Regular 87"]
