"""One line in the history log (audit_log) for an owner action that isn't about a single worksheet."""

import json

from psycopg import Connection

from app.core import db
from app.core.auth import CurrentUser


def log(conn: Connection, user: CurrentUser, action: str, details: dict) -> None:
    db.execute(
        conn,
        "insert into audit_log (report_id, actor_id, action, details) values (null, %s, %s, %s)",
        [user.id, action, json.dumps(details, default=str)],
    )
