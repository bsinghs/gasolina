"""HTTP endpoints for worksheets. Thin: each one checks the role, then calls service.py."""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.core import db
from app.core.auth import CurrentUser, current_user, owner_only
from app.core.dates import EARLIEST, business_today
from app.core.errors import bad_request
from app.modules.reports import service
from app.modules.reports.schemas import ApproveIn, History, Report, ReportSummary, ReturnIn, WorksheetIn

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("", response_model=list[ReportSummary])
def list_reports(
    store_id: UUID | None = None,
    status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    mine: bool = False,
    user: CurrentUser = Depends(current_user),
):
    """Filter by store, status (comma-separated), date range. `mine=true` = only my worksheets."""
    with db.transaction() as conn:
        return service.list_reports(
            conn, user, store_id=store_id, status=status, date_from=date_from, date_to=date_to, mine=mine
        )


@router.get("/lookup", response_model=Report | None)
def lookup(store_id: UUID, business_date: date, user: CurrentUser = Depends(current_user)):
    """The worksheet for one store and day, or null if nobody has started it."""
    with db.transaction() as conn:
        report_id = service.find_report_id(conn, store_id, business_date)
        return service.get_report(conn, user, report_id) if report_id else None


@router.get("/history", response_model=History)
def history(until: date | None = None, days: int = Query(default=30, ge=1, le=92), store_id: UUID | None = None,
            user: CurrentUser = Depends(current_user)):
    """My days, one page at a time (newest first) with whole-month totals. `until` defaults to today."""
    until = until or business_today()
    if until < EARLIEST:
        raise bad_request("Pick a date from 2000 on")
    with db.transaction() as conn:
        return service.history(conn, user, until, days, store_id)


@router.get("/payees", response_model=list[str])
def payees(store_id: UUID, user: CurrentUser = Depends(current_user)):
    """Vendor names already used on paid outs at this store, most used first (suggestions for new lines)."""
    with db.transaction() as conn:
        return service.payees(conn, user, store_id)


@router.get("/{report_id}", response_model=Report)
def get_report(report_id: UUID, user: CurrentUser = Depends(current_user)):
    with db.transaction() as conn:
        return service.get_report(conn, user, report_id)


@router.put("", response_model=Report)
def save_worksheet(data: WorksheetIn, user: CurrentUser = Depends(current_user)):
    """Create or update the draft for data.store_id + data.business_date."""
    with db.transaction() as conn:
        report_id = service.save_worksheet(conn, user, data)
        return service.get_report(conn, user, report_id)


@router.post("/{report_id}/submit", response_model=Report)
def submit(report_id: UUID, user: CurrentUser = Depends(current_user)):
    with db.transaction() as conn:
        service.submit(conn, user, report_id)
        return service.get_report(conn, user, report_id)


@router.post("/{report_id}/return", response_model=Report)
def return_to_employee(report_id: UUID, data: ReturnIn, user: CurrentUser = Depends(owner_only)):
    with db.transaction() as conn:
        service.return_to_employee(conn, user, report_id, data.note)
        return service.get_report(conn, user, report_id)


@router.post("/{report_id}/approve", response_model=Report)
def approve(report_id: UUID, data: ApproveIn | None = None, user: CurrentUser = Depends(owner_only)):
    with db.transaction() as conn:
        service.approve(conn, user, report_id, data or ApproveIn())
        return service.get_report(conn, user, report_id)


@router.post("/{report_id}/reopen", response_model=Report)
def reopen(report_id: UUID, user: CurrentUser = Depends(owner_only)):
    with db.transaction() as conn:
        service.reopen(conn, user, report_id)
        return service.get_report(conn, user, report_id)
