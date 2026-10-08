"""The owner's books: typed purchases / expenses, Profit & Loss, Balance Sheet. Owner only.
Routers check the role; service.py fetches rows; math.py does the math."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.core import db
from app.core.auth import CurrentUser, owner_only
from app.core.errors import bad_request
from app.core.json import exact
from app.modules.books import service
from app.modules.books.schemas import BalanceIn, EntryIn, check_month

router = APIRouter(prefix="/books", tags=["books"])
Include = Literal["approved", "submitted"]


def _month(month: str = Query(..., description="2026-10")) -> str:
    try:
        return check_month(month)
    except ValueError as e:
        raise bad_request(str(e)) from None


@router.get("/entries")
def list_entries(month: str = Depends(_month), store_id: UUID | None = None, _: CurrentUser = Depends(owner_only)):
    with db.transaction() as conn:
        return exact(service.list_entries(conn, month, store_id))


@router.post("/entries")
def add_entry(data: EntryIn, user: CurrentUser = Depends(owner_only)):
    with db.transaction() as conn:
        return exact(service.add_entry(conn, user, data))


@router.patch("/entries/{entry_id}")
def update_entry(entry_id: UUID, data: EntryIn, user: CurrentUser = Depends(owner_only)):
    with db.transaction() as conn:
        return exact(service.update_entry(conn, user, entry_id, data))


@router.delete("/entries/{entry_id}")
def delete_entry(entry_id: UUID, user: CurrentUser = Depends(owner_only)):
    with db.transaction() as conn:
        service.delete_entry(conn, user, entry_id)
    return {"ok": True}


@router.get("/pnl")
def pnl(month: str = Depends(_month), store_id: UUID | None = None, include: Include = "approved",
        count_paid_outs: bool = True, _: CurrentUser = Depends(owner_only)):
    with db.transaction() as conn:
        return exact(service.profit_and_loss(conn, month, store_id, include, count_paid_outs))


@router.get("/pnl-year")
def pnl_year(year: str, store_id: UUID | None = None, include: Include = "approved",
             count_paid_outs: bool = True, _: CurrentUser = Depends(owner_only)):
    with db.transaction() as conn:
        return exact(service.profit_and_loss_year(conn, year, store_id, include, count_paid_outs))


@router.get("/balance")
def balance(month: str = Depends(_month), store_id: UUID | None = None, include: Include = "approved",
            count_paid_outs: bool = True, _: CurrentUser = Depends(owner_only)):
    with db.transaction() as conn:
        return exact(service.balance(conn, month, store_id, include, count_paid_outs))


@router.put("/balance")
def save_balance(data: BalanceIn, user: CurrentUser = Depends(owner_only)):
    with db.transaction() as conn:
        service.save_balance(conn, user, data)
        return exact(service.balance(conn, data.month, data.store_id, "approved"))


@router.post("/balance/copy-previous")
def copy_previous(month: str = Depends(_month), store_id: UUID | None = None, user: CurrentUser = Depends(owner_only)):
    with db.transaction() as conn:
        copied = service.copy_previous(conn, user, month, store_id)
        return exact({"copied": copied, **service.balance(conn, month, store_id, "approved")})
