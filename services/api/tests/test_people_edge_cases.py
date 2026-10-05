"""Edge cases found by the independent QA review of delete-and-deactivate (Oct 4, 2026).
Each test once failed on the reviewed code; they now guard against the bugs coming back.
Skipped unless TEST_DATABASE_URL points at an empty test database."""

import os

import pytest

TEST_DB = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DB, reason="set TEST_DATABASE_URL to run")

OWNER = {"X-Dev-Email": "owner@example.com"}


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

    # Return 500s as responses instead of raising, so the tests show the status the browser would get
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def _store(client, name):
    r = client.post("/api/stores", json={"name": name}, headers=OWNER)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_duplicate_store_ids_on_edit(client):
    s = _store(client, "Dup Edit")
    p = client.post("/api/people", json={"email": "dup1@example.com", "store_ids": [s]}, headers=OWNER).json()
    body = {"email": "dup1@example.com", "name": "D", "role": "employee", "store_ids": [s, s]}
    r = client.patch(f"/api/people/{p['id']}", json=body, headers=OWNER)
    # store_members PK violation escapes update_person -> 500
    assert r.status_code in (200, 400), (r.status_code, r.text)


def test_duplicate_store_ids_on_invite(client):
    s = _store(client, "Dup Invite")
    r = client.post("/api/people", json={"email": "dup2@example.com", "store_ids": [s, s]}, headers=OWNER)
    # PK violation on store_members is caught as UniqueViolation -> "Someone with that email is already on the list"
    assert not (r.status_code == 409 and "email" in r.json()["detail"]), r.text


def test_change_email_to_existing_is_409(client):
    s = _store(client, "Email Clash")
    client.post("/api/people", json={"email": "first@example.com", "store_ids": [s]}, headers=OWNER)
    p = client.post("/api/people", json={"email": "second@example.com", "store_ids": [s]}, headers=OWNER).json()
    body = {"email": "first@example.com", "name": "S", "role": "employee", "store_ids": [s]}
    r = client.patch(f"/api/people/{p['id']}", json=body, headers=OWNER)
    assert r.status_code == 409, (r.status_code, r.text)


def test_cant_delete_a_store_someone_only_works_at(client):
    s = _store(client, "Only Store")
    p = client.post("/api/people", json={"email": "lonely@example.com", "store_ids": [s]}, headers=OWNER).json()
    r = client.delete(f"/api/stores/{s}", headers=OWNER)
    assert r.status_code == 409 and "only work" in r.json()["detail"], r.text
    person = next(x for x in client.get("/api/people", headers=OWNER).json() if x["id"] == p["id"])
    assert person["store_ids"] == [s]


def test_admin_can_not_be_given_admin_email_by_owner_rename(client):
    """Sanity check (should PASS): owner can't take over the admin's email via rename."""
    s = _store(client, "Admin Clash")
    p = client.post("/api/people", json={"email": "x@example.com", "store_ids": [s]}, headers=OWNER).json()
    body = {"email": "admin@example.com", "name": "X", "role": "owner", "store_ids": []}
    r = client.patch(f"/api/people/{p['id']}", json=body, headers=OWNER)
    assert r.status_code != 200
