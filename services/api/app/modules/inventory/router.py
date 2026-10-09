"""Inventory (owner / co-owner): fuel tanks and merchandise per store for a month. Read-only:
deliveries and purchases are added through /api/books/entries."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends

from app.core import db
from app.core.auth import CurrentUser, owner_only
from app.core.dates import business_today
from app.core.json import exact
from app.modules.books.router import _month
from app.modules.inventory import service

router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.get("")
def inventory(month: str = Depends(_month), store_id: UUID | None = None,
              include: Literal["approved", "submitted"] = "approved", _: CurrentUser = Depends(owner_only)):
    with db.transaction() as conn:
        return exact(service.inventory(conn, month, store_id, include, business_today()))
