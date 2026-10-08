"""Vendor list (owner): who the stores pay, and whether that's cost of goods or an expense."""

from datetime import date
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends

from app.core import db
from app.core.auth import CurrentUser, owner_only
from app.core.json import exact
from app.modules.summaries.service import period_range
from app.modules.vendors import service
from app.modules.vendors.schemas import Vendor, VendorIn

router = APIRouter(prefix="/vendors", tags=["vendors"])


@router.get("", response_model=list[Vendor])
def list_vendors(_: CurrentUser = Depends(owner_only)):
    with db.transaction() as conn:
        return service.list_vendors(conn)


@router.post("", response_model=Vendor)
def add_vendor(data: VendorIn, user: CurrentUser = Depends(owner_only)):
    with db.transaction() as conn:
        return service.add(conn, user, data)


@router.patch("/{vendor_id}", response_model=Vendor)
def update_vendor(vendor_id: UUID, data: VendorIn, user: CurrentUser = Depends(owner_only)):
    with db.transaction() as conn:
        return service.update(conn, user, vendor_id, data)


@router.delete("/{vendor_id}")
def delete_vendor(vendor_id: UUID, user: CurrentUser = Depends(owner_only)):
    with db.transaction() as conn:
        service.delete(conn, user, vendor_id)
    return {"ok": True}


@router.get("/spending")
def spending(period: Literal["month", "year"], value: str, store_id: UUID | None = None,
             include: Literal["approved", "submitted"] = "approved", _: CurrentUser = Depends(owner_only)):
    first, last, label = period_range(period, value)
    with db.transaction() as conn:
        return exact({"label": label, **service.spending(conn, first, last, store_id, include)})
