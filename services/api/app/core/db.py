"""Database access: a connection pool plus three small helpers.

Usage:
    with transaction() as conn:
        row = fetch_one(conn, "select * from stores where id = %s", [store_id])
"""

from contextlib import contextmanager
from typing import Any, Iterator

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.core.config import get_settings

_pool: ConnectionPool | None = None


def open_pool() -> None:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            get_settings().database_url,
            min_size=1,
            max_size=5,
            kwargs={"row_factory": dict_row, "prepare_threshold": None},
            open=True,
        )


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


@contextmanager
def transaction() -> Iterator[Connection]:
    """A connection whose work is committed together, or rolled back on any error."""
    open_pool()
    assert _pool is not None
    with _pool.connection() as conn:
        with conn.transaction():
            yield conn


def fetch_one(conn: Connection, sql: str, params: Any = None) -> dict | None:
    return conn.execute(sql, params).fetchone()


def fetch_all(conn: Connection, sql: str, params: Any = None) -> list[dict]:
    return conn.execute(sql, params).fetchall()


def execute(conn: Connection, sql: str, params: Any = None) -> None:
    conn.execute(sql, params)
