"""Versions and the release log. Skipped unless TEST_DATABASE_URL points at an empty test database."""

import os

import pytest

TEST_DB = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DB, reason="set TEST_DATABASE_URL to run")

OWNER = {"X-Dev-Email": "owner@example.com"}
EMP = {"X-Dev-Email": "relemp@example.com"}


@pytest.fixture(scope="module")
def app_env():
    os.environ.update(DATABASE_URL=TEST_DB, AUTH_MODE="dev", BOOTSTRAP_OWNER_EMAIL="owner@example.com", ADMIN_EMAILS="admin@example.com",
                      APP_ENV="test", GIT_COMMIT="abc1234", DEPLOYED_BY="bhajan@example.com")
    import psycopg

    with psycopg.connect(TEST_DB, autocommit=True) as conn:
        conn.execute("drop schema public cascade; create schema public;")
    from scripts import migrate

    from app.core.config import get_settings
    get_settings.cache_clear()
    migrate.main()
    yield
    os.environ.update(APP_ENV="production", GIT_COMMIT="dev", DEPLOYED_BY="")
    get_settings.cache_clear()


def start(app_env):
    from fastapi.testclient import TestClient

    from app.main import app
    return TestClient(app, raise_server_exceptions=False)


def test_health_shows_version_and_commit(app_env):
    from app.core.release import app_version
    with start(app_env) as c:
        h = c.get("/api/health").json()
    assert h == {"ok": True, "env": "test", "version": app_version(), "commit": "abc1234"}
    assert app_version().count(".") == 2


def test_release_log_one_row_per_new_version_or_commit(app_env):
    from app.core.config import get_settings
    for _ in range(3):                       # restarts with the same build: still one row
        with start(app_env):
            pass
    with start(app_env) as c:
        log = c.get("/api/releases", headers=OWNER).json()
    assert [(r["env"], r["git_commit"]) for r in log] == [("test", "abc1234")]
    assert "deployed_by" not in log[0]                                         # kept in the database, not shown

    os.environ["GIT_COMMIT"] = "def5678"; get_settings.cache_clear()
    with start(app_env) as c:
        log = c.get("/api/releases", headers=OWNER).json()
        assert [r["git_commit"] for r in log] == ["def5678", "abc1234"]           # newest first
        # staff can't read the release log; anyone can read health
        c.post("/api/people", json={"email": "relemp@example.com", "store_ids": []}, headers=OWNER)
        assert c.get("/api/releases", headers=EMP).status_code in (403, 401)
        assert c.get("/api/health").status_code == 200
