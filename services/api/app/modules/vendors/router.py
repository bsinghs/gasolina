"""Vendor list (owner): who the stores pay, and whether that's cost of goods or an expense."""

from datetime import date
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.core import db
from app.core.auth import CurrentUser, current_user, owner_only
from app.core.json import exact
from app.modules.reports.schemas import MISCELLANEOUS
from app.modules.summaries.service import period_range
from app.modules.vendors import service
from app.modules.vendors.schemas import Vendor, VendorIn

router = APIRouter(prefix="/vendors", tags=["vendors"])


@router.get("/names")
def vendor_names(_: CurrentUser = Depends(current_user)):
    """Active vendors for the paid-out dropdown on the worksheet (anyone signed in). Name and type only."""
    with db.transaction() as conn:
        return db.fetch_all(conn, "select name, kind from vendors where active order by lower(name)")


@router.get("/miscellaneous")
def miscellaneous(days: int = Query(default=90, ge=1, le=366), _: CurrentUser = Depends(owner_only)):
    """Paid outs marked Miscellaneous in the last `days` days, with the note, so the owner can add the vendor."""
    with db.transaction() as conn:
        return exact(db.fetch_all(
            conn,
            """select p.id, p.amount, p.kind, p.note, r.id as report_id, r.business_date, r.status, s.name as store_name,
                      sp.name as submitted_by_name
               from paid_outs p join daily_reports r on r.id = p.report_id join stores s on s.id = r.store_id
               left join people sp on sp.id = r.submitted_by
               where lower(trim(p.payee)) = lower(%s) and r.business_date >= current_date - %s
                 and r.status <> 'draft'
               order by r.business_date desc, s.name, p.position""",
            [MISCELLANEOUS, days],
        ))


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
