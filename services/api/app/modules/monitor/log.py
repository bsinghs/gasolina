"""The request log behind the admin Monitor page: one row per API request (docs/features/admin-monitor.md).

Written after the answer has been sent, and never allowed to fail a request.
Not logged: /api/health (keep-warm every 5 minutes) and OPTIONS (browser pre-flight).
"""

import logging
import re
import time
from dataclasses import astuple, dataclass
from uuid import UUID

from fastapi import FastAPI, Request
from starlette.background import BackgroundTask
from starlette.concurrency import run_in_threadpool

from app.core import db

log = logging.getLogger("monitor")

PING_ROUTE = "/api/me/ping"
SKIP_PATHS = {"/api/health"}
KEEP_DAYS = 90
_ID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}|\b\d+\b")


@dataclass(frozen=True)
class Row:
    person_id: UUID | None
    viewed_as: UUID | None
    method: str
    route: str
    page: str | None
    status: int
    ms: int
    device: str | None


def device_of(user_agent: str | None) -> str | None:
    ua = user_agent or ""
    if not ua:
        return None
    if "iPad" in ua or "Tablet" in ua:
        return "tablet"
    if "Mobi" in ua or "Android" in ua or "iPhone" in ua:
        return "phone"
    return "computer"


def clean_page(page: str | None) -> str | None:
    """The screen path the web app sends (X-Page), with ids replaced so screens group together."""
    if not page:
        return None
    page = page.split("?", 1)[0].split("#", 1)[0][:80]
    return _ID.sub(":id", page) or "/"


def route_of(request: Request) -> str:
    """The route template (/api/reports/{report_id}), so ids and values never reach the log."""
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    return path or _ID.sub("{id}", request.url.path)[:120]


def write(row: Row) -> None:
    try:
        with db.transaction() as conn:
            db.execute(
                conn,
                """insert into api_requests (person_id, viewed_as, method, route, page, status, ms, device)
                   values (%s, %s, %s, %s, %s, %s, %s, %s)""",
                list(astuple(row)),
            )
    except Exception:  # the log must never break the app
        log.exception("couldn't write the request log")


def remove_old() -> None:
    """Called when the API starts: keep 90 days."""
    try:
        with db.transaction() as conn:
            db.execute(conn, "delete from api_requests where at < now() - make_interval(days => %s)", [KEEP_DAYS])
    except Exception:
        log.exception("couldn't trim the request log")


def install(app: FastAPI) -> None:
    @app.middleware("http")
    async def log_request(request: Request, call_next):
        path = request.url.path
        if request.method == "OPTIONS" or path in SKIP_PATHS or not path.startswith("/api/"):
            return await call_next(request)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            await run_in_threadpool(write, _row(request, 500, started))   # the app crashed: log it, then let it fail
            raise
        _after(response, _row(request, response.status_code, started))
        return response


def _row(request: Request, status: int, started: float) -> Row:
    return Row(
        person_id=getattr(request.state, "person_id", None),
        viewed_as=getattr(request.state, "viewed_as", None),
        method=request.method,
        route=route_of(request),
        page=clean_page(request.headers.get("x-page")),
        status=status,
        ms=round((time.perf_counter() - started) * 1000),
        device=device_of(request.headers.get("user-agent")),
    )


def _after(response, row: Row) -> None:
    """Run the write after the answer has been sent, keeping any background work the route already had."""
    earlier = response.background

    async def both():
        if earlier is not None:
            await earlier()
        await _run(row)

    response.background = BackgroundTask(both)


async def _run(row: Row) -> None:
    await run_in_threadpool(write, row)
