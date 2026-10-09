"""Owner's Oct 8 call (spec: docs/features/owner-call-oct9.md), through the API against a real database:
My days history, co-owner, tank setup, fuel deliveries, Inventory, vendor dropdown + Miscellaneous.
Skipped unless TEST_DATABASE_URL points at an empty test database."""

import os
from datetime import date, timedelta

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
        {"name": "Tank 1 – Regular", "grade": "Regular", "capacity": 10000},
        {"name": "Tank 2 – Premium", "grade": "Premium", "capacity": 5000}]}, headers=OWNER))
    b = ok(client.post("/api/stores", json={"name": "Store B"}, headers=OWNER))
    ok(client.post("/api/people", json={"email": "emp@example.com", "name": "Emma", "store_ids": [a["id"]]}, headers=OWNER))
    ok(client.post("/api/people", json={"email": "empb@example.com", "name": "Ben", "store_ids": [b["id"]]}, headers=OWNER))
    ok(client.post("/api/people", json={"email": "co@example.com", "name": "Cora", "role": "coowner"}, headers=OWNER))
    return {"a": a, "b": b}


def day(client, store, d, fuel="0", merch="0", gallons="0", drop=None, paid_outs=(), tanks=None, submit=True,
        approve=False, who=EMP):
    total = f"{float(fuel) + float(merch):.2f}"
    r = ok(client.put("/api/reports", json={
        "store_id": store["id"], "business_date": d, "fuel_sale": fuel, "merch_sale": merch, "gallons": gallons,
        "cash_drop": drop or total, "paid_outs": list(paid_outs),
        "tank_inventory": [{"tank": k, "gallons": v} for k, v in (tanks or {}).items()]}, headers=who))
    if submit:
        ok(client.post(f"/api/reports/{r['id']}/submit", headers=who))
    if approve:
        ok(client.post(f"/api/reports/{r['id']}/approve", json={}, headers=OWNER))
    return r


# ---------- 1. My days ----------

def test_my_days_history_pages_and_month_totals(client, world):
    a, b = world["a"], world["b"]
    day(client, a, "2026-07-01", fuel="100.00", merch="50.00", gallons="30")
    day(client, a, "2026-08-30", fuel="200.00", merch="20.00", gallons="60", drop="215.00")     # short 5
    day(client, a, "2026-08-31", fuel="300.00", merch="30.00", gallons="90", approve=True)
    day(client, a, "2026-08-29", fuel="999.00", submit=False)                                    # draft: not in totals
    ret = day(client, a, "2026-08-28", fuel="400.00")
    ok(client.post(f"/api/reports/{ret['id']}/return", json={"note": "Fix fuel"}, headers=OWNER))  # sent back: not in totals
    day(client, b, "2026-08-30", fuel="777.00", who=EMP_B)                                        # other store

    h = ok(client.get("/api/reports/history?until=2026-08-31&days=30", headers=EMP))
    dates = [(d["business_date"], d["status"]) for d in h["days"]]
    assert dates == [("2026-08-31", "approved"), ("2026-08-30", "submitted"), ("2026-08-29", "draft"), ("2026-08-28", "returned")]
    top = h["days"][0]
    assert (top["fuel_sale"], top["merch_sale"], top["gallons"]) == ("300.00", "30.00", "90.0") and top["submitted_at"]
    assert h["days"][2]["submitted_at"] is None
    assert h["months"] == [{"month": "2026-08", "store_id": a["id"], "store_name": "Store A", "days": 2, "days_short": 1,
                            "fuel_sale": "500.00", "merch_sale": "50.00", "gallons": "150.0", "over_short": "-5.00"}]
    assert h["next_until"] == "2026-07-01"            # skips the empty stretch to the next older worksheet

    older = ok(client.get(f"/api/reports/history?until={h['next_until']}&days=30", headers=EMP))
    assert [d["business_date"] for d in older["days"]] == ["2026-07-01"] and older["next_until"] is None
    assert older["months"][0]["month"] == "2026-07" and older["months"][0]["fuel_sale"] == "100.00"

    # Store B's employee sees only Store B
    hb = ok(client.get("/api/reports/history?until=2026-08-31&days=30", headers=EMP_B))
    assert {d["store_name"] for d in hb["days"]} == {"Store B"} and [m["store_name"] for m in hb["months"]] == ["Store B"]
    assert ok(client.get("/api/reports/history?until=2026-08-31&days=30", headers=OWNER))["months"][1]["store_name"] == "Store B"

    assert client.get("/api/reports/history?days=0", headers=EMP).status_code == 422
    assert client.get("/api/reports/history?days=93", headers=EMP).status_code == 422
    assert client.get("/api/reports/history", headers=EMP).status_code == 200      # until = today


def test_review_list_has_submit_time(client, world):
    rows = ok(client.get("/api/reports?status=submitted", headers=OWNER))
    assert rows and all(r["submitted_at"] for r in rows) and "fuel_sale" in rows[0]


# ---------- 2. Co-owner ----------

def test_coowner_has_owner_powers(client, world):
    me = ok(client.get("/api/me", headers=CO))
    assert me["role"] == "coowner" and len(me["stores"]) == 2
    for path in ["/api/reports?status=submitted", "/api/summaries?period=month&value=2026-08", "/api/books/pnl?month=2026-08",
                 "/api/settings", "/api/people", "/api/vendors", "/api/inventory?month=2026-08", "/api/vendors/miscellaneous"]:
        assert client.get(path, headers=CO).status_code == 200, path
    waiting = ok(client.get("/api/reports?status=submitted", headers=CO))
    assert ok(client.post(f"/api/reports/{waiting[0]['id']}/approve", json={}, headers=CO))["status"] == "approved"
    # People list shows the role; admins stay hidden
    people = {p["email"]: p for p in ok(client.get("/api/people", headers=CO))}
    assert people["co@example.com"]["role"] == "coowner" and "admin@example.com" not in people


def test_only_the_owner_manages_owners_and_coowners(client, world):
    a = world["a"]
    owner_id = next(p["id"] for p in ok(client.get("/api/people", headers=OWNER)) if p["email"] == "owner@example.com")
    co_id = next(p["id"] for p in ok(client.get("/api/people", headers=OWNER)) if p["email"] == "co@example.com")
    # co-owner can add / edit staff
    new = ok(client.post("/api/people", json={"email": "staff2@example.com", "store_ids": [a["id"]]}, headers=CO))
    ok(client.patch(f"/api/people/{new['id']}", json={"email": "staff2@example.com", "name": "Sam", "role": "manager", "store_ids": [a["id"]]}, headers=CO))
    # … but not owners or co-owners
    assert client.post("/api/people", json={"email": "x@example.com", "role": "coowner"}, headers=CO).status_code == 403
    assert client.post("/api/people", json={"email": "y@example.com", "role": "owner"}, headers=CO).status_code == 403
    assert client.patch(f"/api/people/{new['id']}", json={"email": "staff2@example.com", "role": "owner"}, headers=CO).status_code == 403
    assert client.patch(f"/api/people/{owner_id}", json={"email": "owner@example.com", "role": "employee", "store_ids": [a["id"]]}, headers=CO).status_code == 403
    assert client.patch(f"/api/people/{owner_id}", json={"email": "owner@example.com", "role": "owner", "active": False}, headers=CO).status_code == 403
    assert client.delete(f"/api/people/{owner_id}", headers=CO).status_code == 403
    # can change own name, not own role
    assert ok(client.patch(f"/api/people/{co_id}", json={"email": "co@example.com", "name": "Cora P", "role": "coowner"}, headers=CO))["name"] == "Cora P"
    assert client.patch(f"/api/people/{co_id}", json={"email": "co@example.com", "role": "owner"}, headers=CO).status_code == 400
    # the owner can
    tmp = ok(client.post("/api/people", json={"email": "co2@example.com", "role": "coowner"}, headers=OWNER))
    assert ok(client.delete(f"/api/people/{tmp['id']}", headers=OWNER))["ok"]
    # admin's View as lists the co-owner, and viewing as them is read-only
    opts = ok(client.get("/api/me", headers=ADMIN))["view_as_options"]
    assert any(o["role"] == "coowner" for o in opts)
    view = {**ADMIN, "X-View-As": co_id}
    assert client.get("/api/inventory?month=2026-08", headers=view).status_code == 200
    assert client.post("/api/vendors", json={"name": "Nope", "kind": "expense"}, headers=view).status_code == 403


def test_staff_cant_use_owner_pages(client, world):
    for path in ["/api/inventory?month=2026-08", "/api/vendors/miscellaneous", "/api/vendors"]:
        assert client.get(path, headers=EMP).status_code == 403, path


# ---------- 3. Tanks, deliveries, Inventory ----------

def test_tank_specs_saved_and_kept(client, world):
    a = world["a"]
    stores = {s["name"]: s for s in ok(client.get("/api/stores", headers=OWNER))}
    assert stores["Store A"]["tanks"] == ["Tank 1 – Regular", "Tank 2 – Premium"]
    assert stores["Store A"]["tank_specs"] == [{"name": "Tank 1 – Regular", "grade": "Regular", "capacity": "10000", "aliases": []},
                                               {"name": "Tank 2 – Premium", "grade": "Premium", "capacity": "5000", "aliases": []}]
    # Store B: default tanks, fuel type guessed from the name, size unknown
    assert [(t["grade"], t["capacity"]) for t in stores["Store B"]["tank_specs"]] == [("Regular", None), ("Regular", None), ("Premium", None)]
    # saving the store without specs keeps them; employees see the tank names on /me
    ok(client.patch(f"/api/stores/{a['id']}", json={"name": "Store A"}, headers=OWNER))
    again = next(s for s in ok(client.get("/api/stores", headers=OWNER)) if s["id"] == a["id"])
    assert again["tank_specs"][1]["capacity"] == "5000"
    assert client.patch(f"/api/stores/{a['id']}", json={"name": "Store A", "tank_specs": [{"name": "T", "grade": "Kerosene"}]}, headers=OWNER).status_code == 422
    assert client.patch(f"/api/stores/{a['id']}", json={"name": "Store A", "tank_specs": [{"name": "T", "capacity": -5}]}, headers=OWNER).status_code == 422


@pytest.fixture(scope="module")
def september(client, world):
    """Worked example (same numbers as test_inventory_math.py): Store A, Aug 31 - Sep 3."""
    a = world["a"]
    vendors = {n: ok(client.post("/api/vendors", json={"name": n, "kind": k}, headers=OWNER))
               for n, k in [("Reed Oil", "fuel"), ("McLane", "merchandise"), ("Pepsi", "merchandise"), ("Coke", "merchandise"), ("Ice Co", "expense")]}
    T1, T2 = "Tank 1 – Regular", "Tank 2 – Premium"
    # Aug 31 was approved earlier in the history test; reopen to add readings, then approve again
    rid = ok(client.get(f"/api/reports/lookup?store_id={a['id']}&business_date=2026-08-31", headers=OWNER))["id"]
    ok(client.post(f"/api/reports/{rid}/reopen", headers=OWNER))
    ok(client.put("/api/reports", json={"store_id": a["id"], "business_date": "2026-08-31", "fuel_sale": "300.00", "merch_sale": "30.00",
                                        "gallons": "900", "cash_drop": "320.00", "paid_outs": [{"kind": "cash", "payee": "Coke", "amount": "10.00"}],
                                        "tank_inventory": [{"tank": T1, "gallons": "6000"}, {"tank": T2, "gallons": "3000"}]}, headers=OWNER))
    ok(client.post(f"/api/reports/{rid}/approve", json={}, headers=OWNER))
    day(client, a, "2026-09-01", fuel="3500.00", merch="500.00", gallons="1150", tanks={T1: "5000", T2: "2800"}, approve=True,
        drop="3930.00", paid_outs=[{"kind": "cash", "payee": "pepsi", "amount": "50.00"}, {"kind": "cash", "payee": "Ice Co", "amount": "20.00"}])
    day(client, a, "2026-09-02", fuel="3600.00", merch="600.00", gallons="1200", tanks={T1: "8000", T2: "2600"}, approve=True)
    day(client, a, "2026-09-03", fuel="3000.00", merch="400.00", gallons="1000", tanks={T1: "7100", T2: "2450"}, approve=True)
    day(client, a, "2026-09-04", fuel="1.00", gallons="1", tanks={T1: "1", T2: "1"}, submit=False)   # draft: ignored
    delivery = ok(client.post("/api/books/entries", json={
        "store_id": a["id"], "category": "fuel_purchase", "description": "Reed Oil load, inv 5521", "amount": "10000.00",
        "vendor_id": vendors["Reed Oil"]["id"], "entry_date": "2026-09-02", "tank": T1, "gallons": "4000"}, headers=CO))
    ok(client.post("/api/books/entries", json={
        "store_id": a["id"], "category": "merchandise_purchase", "description": "McLane order", "amount": "300.00",
        "vendor_id": vendors["McLane"]["id"], "entry_date": "2026-09-02"}, headers=OWNER))
    return {"delivery": delivery, "vendors": vendors, "T1": T1, "T2": T2}


def test_delivery_entry_rules(client, world, september):
    a, b, d = world["a"], world["b"], september["delivery"]
    assert d["month"] == "2026-09-01" and d["gallons"] == "4000.0" and d["tank"] == september["T1"]
    base = {"store_id": a["id"], "category": "fuel_purchase", "description": "Load", "amount": "1.00", "entry_date": "2026-09-05", "gallons": "10"}
    assert client.post("/api/books/entries", json=base | {"tank": "Tank 9"}, headers=OWNER).status_code == 400          # not this store's tank
    assert client.post("/api/books/entries", json=base | {"tank": "Tank 2 – Premium", "store_id": b["id"]}, headers=OWNER).status_code == 400
    assert client.post("/api/books/entries", json=base | {"tank": "Tank 1 – Regular", "category": "expense"}, headers=OWNER).status_code == 400
    assert client.post("/api/books/entries", json={**base, "tank": "Tank 1 – Regular", "entry_date": None, "month": "2026-09"}, headers=OWNER).status_code == 400
    assert client.post("/api/books/entries", json=base | {"tank": "Tank 1 – Regular", "store_id": None}, headers=OWNER).status_code == 400
    assert client.post("/api/books/entries", json=base | {"tank": "Tank 1 – Regular", "month": "2026-10"}, headers=OWNER).status_code == 422
    assert client.post("/api/books/entries", json=base | {"tank": "Tank 1 – Regular", "gallons": "0"}, headers=OWNER).status_code == 422
    assert client.post("/api/books/entries", json=base | {"tank": "Tank 1 – Regular", "entry_date": "1999-12-31"}, headers=OWNER).status_code == 422
    assert client.post("/api/books/entries", json=base | {"tank": "Tank 1 – Regular"}, headers=EMP).status_code == 403
    assert client.post("/api/books/entries", json=base | {"tank": "Tank 1 – Regular", "entry_date": "2099-01-01", "month": None}, headers=OWNER).status_code == 400

    # Editing on the P&L screen (no date / tank / gallons sent) keeps them
    pnl_edit = {"month": "2026-09", "store_id": a["id"], "category": "fuel_purchase", "description": "Reed Oil load, inv 5521 (paid)",
                "amount": "10000.00", "vendor_id": d["vendor_id"]}
    e = ok(client.patch(f"/api/books/entries/{d['id']}", json=pnl_edit, headers=OWNER))
    assert (e["entry_date"], e["tank"], e["gallons"], e["description"]) == ("2026-09-02", september["T1"], "4000.0", "Reed Oil load, inv 5521 (paid)")
    # … but not if that would break the delivery
    assert client.patch(f"/api/books/entries/{d['id']}", json=pnl_edit | {"category": "expense"}, headers=OWNER).status_code == 400
    assert client.patch(f"/api/books/entries/{d['id']}", json=pnl_edit | {"month": "2026-08"}, headers=OWNER).status_code == 400
    assert client.patch(f"/api/books/entries/{d['id']}", json=pnl_edit | {"store_id": None}, headers=OWNER).status_code == 400
    # history keeps the delivery fields
    pnl = ok(client.get(f"/api/books/pnl?month=2026-09&store_id={a['id']}", headers=OWNER))
    assert pnl["cost_lines"][0]["label"] == "Fuel purchases" and pnl["cost_lines"][0]["amount"] == "10000.00"   # counted once


def test_inventory_worked_example(client, world, september):
    a = world["a"]
    inv = ok(client.get(f"/api/inventory?month=2026-09&store_id={a['id']}", headers=OWNER))
    assert inv["label"].startswith("September") and inv["reorder_percent"] == 25 and inv["as_of"] == "2026-09-30"
    s = inv["stores"][0]
    t1, t2 = s["fuel"]["tanks"]
    assert (t1["used"], t1["average_per_day"], t1["latest"], t1["percent_full"], t1["days_left"], t1["delivered"]) == \
           ("2900.0", "966.7", "7100.0", "71.0", "7.3", "4000.0")
    assert (t2["used"], t2["percent_full"], t2["days_left"], t2["order_soon"]) == ("550.0", "49.0", "13.4", False)
    assert [g["grade"] for g in s["fuel"]["grades"]] == ["Regular", "Premium"]
    c = s["fuel"]["pump_check"]
    assert (c["first_day"], c["last_day"], c["pump_gallons"], c["tank_gallons"], c["difference"], c["difference_percent"]) == \
           ("2026-09-01", "2026-09-03", "3350.0", "3450.0", "100.0", "3.0")
    m = s["fuel"]["money"]
    assert (m["sales"], m["gallons_sold"], m["price_per_gallon"], m["cost_per_gallon"], m["margin_per_gallon"]) == \
           ("10100.00", "3350.0", "3.015", "2.500", "0.515")
    assert [(d["entry_date"], d["gallons"], d["vendor_name"]) for d in s["fuel"]["deliveries"]] == [("2026-09-02", "4000.0", "Reed Oil")]
    mer = s["merchandise"]
    assert (mer["sold"], mer["bought_typed"], mer["bought_paid_outs"], mer["bought"], mer["bought_percent_of_sales"]) == \
           ("1500.00", "300.00", "50.00", "350.00", "23.3")
    rows = [(v["vendor"], v["amount"], v["last_day"], v["days_since"]) for v in mer["vendors"]]
    assert rows == [("McLane", "300.00", "2026-09-02", 28), ("Pepsi", "50.00", "2026-09-01", 29), ("Coke", "0", "2026-08-31", 30)]

    # reorder setting flags the Premium tank (49% < 50%)
    settings = ok(client.get("/api/settings", headers=OWNER))
    ok(client.put("/api/settings", json=settings | {"reorder_percent": 50}, headers=OWNER))
    inv2 = ok(client.get(f"/api/inventory?month=2026-09&store_id={a['id']}", headers=CO))
    assert inv2["stores"][0]["fuel"]["tanks"][1]["order_soon"] is True and inv2["stores"][0]["fuel"]["grades"][1]["order_soon"] is True
    ok(client.put("/api/settings", json=settings, headers=OWNER))

    # All stores: one card per active store; Store B has no readings yet
    allinv = ok(client.get("/api/inventory?month=2026-09", headers=OWNER))
    assert [x["store_name"] for x in allinv["stores"]] == ["Store A", "Store B"]
    sb = allinv["stores"][1]["fuel"]
    assert all(t["latest"] is None and t["used"] is None for t in sb["tanks"]) and sb["pump_check"] is None
    assert client.get("/api/inventory?month=2026-13", headers=OWNER).status_code == 400
    # the next month: Aug-Sep readings become the "before" reading; nothing used yet
    oct_ = ok(client.get(f"/api/inventory?month=2026-10&store_id={a['id']}", headers=OWNER))["stores"][0]["fuel"]["tanks"][0]
    assert oct_["latest"] == "7100.0" and oct_["latest_day"] == "2026-09-03" and oct_["used"] is None
    assert oct_["on_hand"] == "7100.0"


# ---------- 4. Vendor dropdown + Miscellaneous ----------

def test_vendor_names_and_submit_rule(client, world, september):
    a = world["a"]
    names = ok(client.get("/api/vendors/names", headers=EMP))
    assert [n["name"] for n in names] == ["Coke", "Ice Co", "McLane", "Pepsi", "Reed Oil"] and set(names[0]) == {"name", "kind"}

    # drafts save anything; submit needs listed names (any case / spacing) or Miscellaneous with a note
    r = day(client, a, "2026-09-10", fuel="100.00", submit=False, paid_outs=[
        {"kind": "cash", "payee": "coca cola", "amount": "5.00"}, {"kind": "check", "payee": "Joe's", "amount": "5.00", "check_no": "1"}])
    bad = client.post(f"/api/reports/{r['id']}/submit", headers=EMP)
    assert bad.status_code == 400 and "coca cola" in bad.json()["detail"] and "Joe's" in bad.json()["detail"]
    r = day(client, a, "2026-09-10", fuel="100.00", submit=False, paid_outs=[
        {"kind": "cash", "payee": " pepsi ", "amount": "5.00"}, {"kind": "cash", "payee": "Miscellaneous", "amount": "7.00"}])
    assert "note" in client.post(f"/api/reports/{r['id']}/submit", headers=EMP).json()["detail"]
    r = day(client, a, "2026-09-10", fuel="100.00", submit=False, paid_outs=[
        {"kind": "cash", "payee": "pepsi", "amount": "5.00"},
        {"kind": "cash", "payee": "Miscellaneous", "amount": "7.00", "note": "  Window cleaner,   Joe's Hardware "}])
    done = ok(client.post(f"/api/reports/{r['id']}/submit", headers=EMP))
    assert done["status"] == "submitted"
    assert [p["note"] for p in done["paid_outs"]] == [None, "Window cleaner, Joe's Hardware"]
    assert client.put("/api/reports", json={"store_id": a["id"], "business_date": "2026-09-11", "paid_outs": [
        {"kind": "cash", "payee": "Miscellaneous", "amount": "1.00", "note": "x" * 301}]}, headers=EMP).status_code == 422

    misc = ok(client.get("/api/vendors/miscellaneous?days=366", headers=OWNER))
    assert [(m["business_date"], m["amount"], m["note"], m["store_name"]) for m in misc] == \
           [("2026-09-10", "7.00", "Window cleaner, Joe's Hardware", "Store A")]
    # the owner can still approve old days with old spellings (the rule is only on submit)
    ok(client.post(f"/api/reports/{r['id']}/approve", json={}, headers=OWNER))


def test_no_vendor_list_means_any_name(client, world):
    """Before the owner adds vendors, names are free (checked in a fresh database by the other test files too)."""
    import psycopg

    with psycopg.connect(TEST_DB, autocommit=True) as conn:
        conn.execute("update vendors set active = false")
    r = day(client, world["b"], "2026-09-12", fuel="10.00", who=EMP_B, submit=False,
            paid_outs=[{"kind": "cash", "payee": "Anyone at all", "amount": "1.00"}])
    assert ok(client.post(f"/api/reports/{r['id']}/submit", headers=EMP_B))["status"] == "submitted"
    assert ok(client.get("/api/vendors/names", headers=EMP_B)) == []
    with psycopg.connect(TEST_DB, autocommit=True) as conn:
        conn.execute("update vendors set active = true")
