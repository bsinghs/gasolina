"""Full API flow against a real Postgres: employee submits, owner sends back, employee fixes,
owner approves and exports. Skipped unless TEST_DATABASE_URL points at an empty test database."""

import os

import pytest

TEST_DB = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DB, reason="set TEST_DATABASE_URL to run")

OWNER = {"X-Dev-Email": "owner@example.com"}
EMP = {"X-Dev-Email": "emp@example.com"}
OTHER = {"X-Dev-Email": "other@example.com"}


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

    with TestClient(app) as c:
        yield c


def test_full_day(client):
    store = client.post("/api/stores", json={"name": "Route 9", "qb_location": "R9"}, headers=OWNER).json()
    other_store = client.post("/api/stores", json={"name": "Main St"}, headers=OWNER).json()
    client.post("/api/people", json={"email": "emp@example.com", "name": "Jo", "store_ids": [store["id"]]}, headers=OWNER)
    client.post("/api/people", json={"email": "other@example.com", "name": "Al", "store_ids": [other_store["id"]]}, headers=OWNER)

    # strangers are refused
    assert client.get("/api/me", headers={"X-Dev-Email": "nobody@example.com"}).status_code == 403
    assert [s["name"] for s in client.get("/api/me", headers=EMP).json()["stores"]] == ["Route 9"]

    worksheet = {
        "store_id": store["id"], "business_date": "2026-10-03",
        "fuel_sale": "4200.00", "merch_sale": "1350.00", "sales_tax": "94.50", "gallons": "1234.5",
        "credit": "3100.00", "debit": "620.00", "ebt": "85.00", "cash_drop": "1790.00",
        "paid_outs": [
            {"kind": "cash", "payee": "Ice vendor", "amount": "40.00"},
            {"kind": "check", "check_no": "1042", "payee": "Beverage distributor", "amount": "312.00"},
        ],
    }
    r = client.put("/api/reports", json=worksheet, headers=EMP)
    assert r.status_code == 200, r.text
    report = r.json()
    assert report["over_short"] == "-9.50" and report["status"] == "draft"

    # another store's employee can't see or write it
    assert client.get(f"/api/reports/{report['id']}", headers=OTHER).status_code == 403
    assert client.put("/api/reports", json=worksheet, headers=OTHER).status_code == 403

    rid = report["id"]
    assert client.post(f"/api/reports/{rid}/submit", headers=EMP).json()["status"] == "submitted"
    assert client.put("/api/reports", json=worksheet, headers=EMP).status_code == 409  # locked after submit
    assert client.post(f"/api/reports/{rid}/approve", headers=EMP).status_code == 403  # employees can't approve

    r = client.post(f"/api/reports/{rid}/return", json={"note": "Recheck debit"}, headers=OWNER).json()
    assert r["status"] == "returned" and r["review_note"] == "Recheck debit"

    worksheet["cash_drop"] = "1799.50"
    assert client.put("/api/reports", json=worksheet, headers=EMP).json()["over_short"] == "0.00"
    client.post(f"/api/reports/{rid}/submit", headers=EMP)

    cash_line = next(p for p in client.get(f"/api/reports/{rid}", headers=OWNER).json()["paid_outs"] if p["kind"] == "cash")
    r = client.post(f"/api/reports/{rid}/approve", json={"gl_accounts": {cash_line["id"]: "Supplies"}}, headers=OWNER)
    assert r.json()["status"] == "approved"

    preview = client.get(f"/api/exports/journal-entry/{rid}", headers=OWNER).json()
    assert sum(float(l["debit"]) for l in preview) == sum(float(l["credit"]) for l in preview) == 5644.50

    csv = client.post("/api/exports/quickbooks", json={"date_from": "2026-10-01", "date_to": "2026-10-31"}, headers=OWNER)
    assert csv.status_code == 200 and "Supplies,40.00" in csv.text and "Location" in csv.text
    assert client.get(f"/api/reports/{rid}", headers=OWNER).json()["status"] == "exported"

    history = [h["action"] for h in client.get(f"/api/reports/{rid}", headers=OWNER).json()["history"]]
    assert history[0] == "exported" and "returned" in history


def test_app_admin(client):
    """ADMIN_EMAILS people get owner powers, show on People as admin, and the owner can't change them."""
    from app.core.auth import bootstrap_admins

    bootstrap_admins()  # the fixture sets ADMIN_EMAILS=admin@example.com
    admin = {"X-Dev-Email": "admin@example.com"}
    assert client.get("/api/me", headers=admin).json()["role"] == "admin"
    assert client.get("/api/settings", headers=admin).status_code == 200  # owner-only page
    store = client.post("/api/stores", json={"name": "Admin-made store"}, headers=admin)
    assert store.status_code == 200

    people = client.get("/api/people", headers=OWNER).json()
    row = next(p for p in people if p["email"] == "admin@example.com")
    assert row["role"] == "admin"
    change = {"email": "admin@example.com", "name": "x", "role": "employee", "active": False, "store_ids": []}
    assert client.patch(f"/api/people/{row['id']}", json=change, headers=OWNER).status_code == 403
    # and the owner can't hand out the admin role
    bad = {"email": "new@example.com", "name": "N", "role": "admin", "store_ids": []}
    assert client.post("/api/people", json=bad, headers=OWNER).status_code == 422
