"""Which version of the API is running, and the release log (one row per new version or commit per environment)."""

from functools import lru_cache
from pathlib import Path

from app.core import db
from app.core.config import get_settings

# VERSION sits at the repo root: <root>/services/api/app/core/release.py (locally, and /srv in the API image)
_CANDIDATES = [Path(__file__).resolve().parents[4] / "VERSION"]


@lru_cache
def app_version() -> str:
    for path in _CANDIDATES:
        if path.is_file():
            return path.read_text().strip() or "unknown"
    return "unknown"


def running() -> dict:
    s = get_settings()
    return {"version": app_version(), "commit": s.git_commit, "env": s.app_env}


def record_release() -> None:
    """Called when the API starts. Cloud Run restarts often, so only a new version or commit adds a row."""
    s = get_settings()
    version, commit = app_version(), s.git_commit
    with db.transaction() as conn:
        last = db.fetch_one(
            conn, "select version, git_commit from releases where env = %s order by started_at desc, id desc limit 1", [s.app_env]
        )
        if last and last["version"] == version and last["git_commit"] == commit:
            return
        db.execute(
            conn, "insert into releases (env, version, git_commit, deployed_by) values (%s, %s, %s, %s)",
            [s.app_env, version, commit, s.deployed_by or None],
        )


def release_log(limit: int = 50) -> list[dict]:
    with db.transaction() as conn:
        return db.fetch_all(
            conn,
            # who deployed stays in the database for the record, but isn't shown in the app
            "select env, version, git_commit, started_at from releases order by started_at desc, id desc limit %s",
            [limit],
        )
