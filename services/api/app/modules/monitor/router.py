"""Admin Monitor: live traffic, who's online, usage and history. App admin only (docs/features/admin-monitor.md)."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.core import db
from app.core.auth import CurrentUser, admin_only
from app.modules.monitor import service

router = APIRouter(prefix="/monitor", tags=["monitor"])


@router.get("/live")
def live(include_me: bool = False, user: CurrentUser = Depends(admin_only)):
    with db.transaction() as conn:
        return service.live(conn, None if include_me else user.id)


@router.get("/usage")
def usage(period: Literal["release", "today", "7d", "30d"] = "release", include_me: bool = False,
          user: CurrentUser = Depends(admin_only)):
    with db.transaction() as conn:
        return service.usage(conn, period, None if include_me else user.id)


@router.get("/history")
def history(person_id: UUID | None = None,
            kind: Literal["worksheet", "vendor", "books", "person", "store", "settings"] | None = None,
            before: int | None = Query(default=None, ge=1), limit: int = Query(default=50, ge=1, le=200),
            _: CurrentUser = Depends(admin_only)):
    with db.transaction() as conn:
        people = db.fetch_all(conn, "select id, name, role from people order by name")
        return {**service.history(conn, person_id, kind, before, limit), "people": people}
