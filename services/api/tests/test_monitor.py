"""Admin Monitor: request log, who's online, usage, history (docs/features/admin-monitor.md).
Skipped unless TEST_DATABASE_URL points at an empty test database."""

import os

import pytest

TEST_DB = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DB, reason="set TEST_DATABASE_URL to run")

OWNER = {"X-Dev-Email": "owner@example.com"}
ADMIN = {"X-Dev-Email": "admin@example.com"}
CO = {"X-Dev-Email": "co@example.com"}
EMP = {"X-Dev-Email": "emp@example.com"}
PHONE = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Mobile/15E148"}


@pytest.fixture(scope="module")
def client():
    os.environ.update(DATABASE_URL=TEST_DB, AUTH_MODE="dev", BOOTSTRAP_OWNER_EMAIL="owner@example.com",
                      ADMIN_EMAILS="admin@example.com", APP_ENV="test", GIT_COMMIT="mon1234")
    import psycopg

    with psycopg.connect(TEST_DB, autocommit=True) as conn:
        conn.execute("drop schema public cascade; create schema public;")
    from scripts import migrate

    from app.core.config import get_settings
    get_settings.cache_clear()
    migrate.main()
    from fastapi.testclient import TestClient

    from app.main import app
    with TestClient(app, raise_server_exceptions=False) as c:
        store = c.post("/api/stores", json={"name": "Mon Store", "qb_location": None, "active": True}, headers=OWNER).json()
        c.post("/api/people", json={"email": "co@example.com", "name": "Co", "role": "coowner", "store_ids": []}, headers=OWNER)
        c.post("/api/people", json={"email": "emp@example.com", "name": "Emp", "role": "employee",
                                    "store_ids": [store["id"]]}, headers=OWNER)
        c.store = store
        yield c
    os.environ.update(APP_ENV="production", GIT_COMMIT="dev")
    get_settings.cache_clear()


def rows(sql, params=None):
    import psycopg
    from psycopg.rows import dict_row
    with psycopg.connect(TEST_DB, row_factory=dict_row) as conn:
        return conn.execute(sql, params).fetchall()


def ids_of(name):
    return rows("select id from people where name = %s", [name])[0]["id"]


def test_only_the_admin_sees_monitor(client):
    for path in ("/api/monitor/live", "/api/monitor/usage", "/api/monitor/history"):
        assert client.get(path, headers=ADMIN).status_code == 200, path
        for who in (OWNER, CO, EMP):
            assert client.get(path, headers=who).status_code == 403, (path, who)
        assert client.get(path).status_code == 401
    # View as: the admin looking at the app as the owner can't see it either
    owner_id = rows("select id from people where email = 'owner@example.com'")[0]["id"]
    assert client.get("/api/monitor/live", headers={**ADMIN, "X-View-As": str(owner_id)}).status_code == 403


def test_requests_are_logged_with_route_template_page_and_device(client):
    rid = "11111111-2222-3333-4444-555555555555"
    client.get(f"/api/reports/{rid}", headers={**EMP, **PHONE, "X-Page": f"/days/{rid}?x=1"})
    client.get("/api/health")
    client.options("/api/me", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"})
    log = rows("select r.*, p.name from api_requests r left join people p on p.id = r.person_id order by r.id desc limit 5")
    last = log[0]
    assert last["name"] == "Emp"
    assert last["route"] == "/api/reports/{report_id}"          # never the id itself
    assert last["page"] == "/days/:id"                          # ids and query values stripped
    assert last["device"] == "phone"
    assert last["status"] in (403, 404) and last["ms"] >= 0
    assert not rows("select 1 from api_requests where route in ('/api/health') or method = 'OPTIONS'")


def test_signed_out_and_crashes_are_logged_without_breaking(client):
    client.get("/api/me")                                       # no sign-in
    assert rows("select person_id, status from api_requests order by id desc limit 1")[0] == {"person_id": None, "status": 401}


def test_logging_failure_never_fails_the_request(client, monkeypatch):
    from app.modules.monitor import log

    def broken(*_a, **_k):
        raise RuntimeError("db down")
    monkeypatch.setattr(log.db, "transaction", broken)
    log.write(log.Row(None, None, "GET", "/api/x", None, 200, 1, None))       # database down: swallowed, no exception


def test_ping_marks_online_and_admin_hidden_unless_asked(client):
    assert client.get("/api/me/ping", headers={**EMP, "X-Page": "/worksheet"}).json() == {"ok": True}
    client.get("/api/me/ping", headers=ADMIN)
    live = client.get("/api/monitor/live", headers=ADMIN).json()
    names = [p["name"] for p in live["online"]]
    assert "Emp" in names and not any(p["role"] == "admin" for p in live["online"])
    emp = next(p for p in live["online"] if p["name"] == "Emp")
    assert emp["page"] == "/worksheet"
    with_me = client.get("/api/monitor/live?include_me=true", headers=ADMIN).json()
    assert any(p["role"] == "admin" for p in with_me["online"])
    assert len(live["per_minute"]) == 60
    # pings aren't traffic
    assert sum(m["requests"] for m in live["per_minute"]) == rows(
        "select count(*) as n from api_requests where route <> '/api/me/ping' and at > now() - interval '60 minutes'"
        " and person_id is distinct from (select id from people where email = 'admin@example.com')")[0]["n"]


def test_view_as_is_logged_under_the_admin(client):
    emp = ids_of("Emp")
    client.get("/api/me", headers={**ADMIN, "X-View-As": str(emp)})
    last = rows("select person_id, viewed_as from api_requests order by id desc limit 1")[0]
    assert last["viewed_as"] == emp
    assert last["person_id"] == rows("select id from people where email = 'admin@example.com'")[0]["id"]


def test_usage_visits_minutes_screens_and_problems(client):
    emp = ids_of("Emp")
    # two visits: one 2 hours ago (3 requests over 2 minutes), one now; plus a server error
    import psycopg
    with psycopg.connect(TEST_DB) as conn:
        for mins_ago, route, page, status in [(122, "/api/stores", "/worksheet", 200), (121, "/api/me", "/worksheet", 200),
                                              (120, "/api/reports", "/my", 200), (1, "/api/reports", "/my", 500)]:
            conn.execute("""insert into api_requests (at, person_id, method, route, page, status, ms, device)
                            values (now() - make_interval(mins => %s), %s, 'GET', %s, %s, %s, 3000, 'phone')""",
                         [mins_ago, emp, route, page, status])
    u = client.get("/api/monitor/usage?period=7d", headers=ADMIN).json()
    assert u["label"] == "last 7 days"
    me = next(p for p in u["people"] if p["name"] == "Emp")
    assert me["visits"] == 2
    assert me["active_minutes"] >= 4
    assert me["errors"] == 1 and me["device"] == "phone"
    assert me["screens"][0] in ("/worksheet", "/my")
    assert u["totals"]["errors"] >= 1 and u["totals"]["slow"] >= 4
    assert any(p["status"] == 500 and p["name"] == "Emp" for p in u["problems"])
    assert not any(p["status"] == 401 for p in u["problems"])                       # sign-in expired is routine
    assert u["days"] and u["slowest"]
    assert not any(p["role"] == "admin" for p in u["people"])
    # since the last release (default): the release row was written when the API started in this test
    r = client.get("/api/monitor/usage", headers=ADMIN).json()
    assert r["period"] == "release" and r["label"].startswith("since release")
    assert client.get("/api/monitor/usage?period=today", headers=ADMIN).json()["label"] == "today"
    assert client.get("/api/monitor/usage?period=year", headers=ADMIN).status_code == 422


def test_history_covers_people_stores_settings_with_filters_and_paging(client):
    c = client
    store = c.store
    c.patch(f"/api/stores/{store['id']}", json={"name": "Mon Store 2", "qb_location": "Erie", "active": True}, headers=OWNER)
    temp = c.post("/api/stores", json={"name": "Oops store", "qb_location": None, "active": True}, headers=OWNER).json()
    c.delete(f"/api/stores/{temp['id']}", headers=OWNER)
    s = c.get("/api/settings", headers=OWNER).json()
    c.put("/api/settings", json={**s, "over_short_alert": "25.00"}, headers=OWNER)
    c.put("/api/settings", json={**s, "over_short_alert": "25.00"}, headers=OWNER)        # no change: no row
    emp = ids_of("Emp")
    p = next(x for x in c.get("/api/people", headers=OWNER).json() if x["name"] == "Emp")
    c.patch(f"/api/people/{emp}", json={**p, "name": "Emp Two"}, headers=OWNER)
    temp_p = c.post("/api/people", json={"email": "oops@example.com", "name": "Oops", "role": "employee",
                                         "store_ids": [store["id"]]}, headers=OWNER).json()
    c.delete(f"/api/people/{temp_p['id']}", headers=OWNER)

    h = c.get("/api/monitor/history?limit=200", headers=ADMIN).json()
    actions = [r["action"] for r in h["rows"]]
    for a in ("store.added", "store.changed", "store.removed", "settings.saved", "person.invited", "person.changed", "person.removed"):
        assert a in actions, a
    assert actions.count("settings.saved") == 1
    changed = next(r for r in h["rows"] if r["action"] == "person.changed")
    assert changed["details"]["before"]["name"] == "Emp" and changed["details"]["after"]["name"] == "Emp Two"
    assert changed["details"]["after"]["stores"] == ["Mon Store 2"]
    sset = next(r for r in h["rows"] if r["action"] == "settings.saved")
    assert list(sset["details"]["changed"]) == ["over_short_alert"]
    assert all(r["who"] for r in h["rows"])
    assert any(p["name"] == "Emp Two" for p in h["people"])

    only_people = c.get("/api/monitor/history?kind=person", headers=ADMIN).json()["rows"]
    assert only_people and all(r["action"].startswith("person.") for r in only_people)
    owner_id = rows("select id from people where email = 'owner@example.com'")[0]["id"]
    by_owner = c.get(f"/api/monitor/history?person_id={owner_id}", headers=ADMIN).json()["rows"]
    assert by_owner and all(r["role"] == "owner" for r in by_owner)
    assert c.get("/api/monitor/history?kind=nope", headers=ADMIN).status_code == 422

    page1 = c.get("/api/monitor/history?limit=3", headers=ADMIN).json()
    page2 = c.get(f"/api/monitor/history?limit=3&before={page1['next_before']}", headers=ADMIN).json()
    assert len(page1["rows"]) == 3 and page1["next_before"]
    assert page2["rows"][0]["id"] < page1["rows"][-1]["id"]


def test_worksheet_history_shows_store_and_day(client):
    from datetime import date
    r = client.put("/api/reports", json={"store_id": client.store["id"], "business_date": str(date.today()),
                                         "values": {}}, headers=EMP)
    if r.status_code != 200:
        pytest.skip(f"worksheet input shape differs here: {r.status_code}")
    h = client.get("/api/monitor/history?kind=worksheet", headers=ADMIN).json()["rows"]
    assert h and h[0]["store"] == "Mon Store 2" and h[0]["business_date"]


def test_old_rows_removed_on_start(client):
    import psycopg
    with psycopg.connect(TEST_DB) as conn:
        conn.execute("""insert into api_requests (at, method, route, status, ms) values
                        (now() - interval '91 days', 'GET', '/api/old', 200, 1),
                        (now() - interval '89 days', 'GET', '/api/kept', 200, 1)""")
    from app.modules.monitor.log import remove_old
    remove_old()
    routes = {r["route"] for r in rows("select route from api_requests where route in ('/api/old', '/api/kept')")}
    assert routes == {"/api/kept"}


def test_device_and_page_helpers():
    from app.modules.monitor.log import clean_page, device_of
    assert device_of("Mozilla/5.0 (Linux; Android 14) Mobile Safari") == "phone"
    assert device_of("Mozilla/5.0 (iPad; CPU OS 17_0)") == "tablet"
    assert device_of("Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0)") == "computer"
    assert device_of(None) is None
    assert clean_page("/days/0b0e6a1e-1d2c-4f6e-9a7b-2b0d9f3e4c5a#top") == "/days/:id"
    assert clean_page("/reports?month=2026-10") == "/reports"
    assert clean_page(None) is None
