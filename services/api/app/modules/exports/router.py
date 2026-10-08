"""Exports for the owner: QuickBooks journal-entry CSV, check paid-outs CSV, raw data CSV,
and a journal-entry preview for one day."""

import csv
import io
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from pydantic import BaseModel

from app.core import db
from app.core.auth import CurrentUser, owner_only
from app.core.errors import bad_request
from app.modules.exports import journal_entry
from app.modules.reports import service as reports
from app.modules.settings.router import load_settings

router = APIRouter(prefix="/exports", tags=["exports"])


class ExportRequest(BaseModel):
    date_from: date
    date_to: date
    store_id: UUID | None = None
    include_already_exported: bool = False


class PreviewLine(BaseModel):
    account: str
    debit: str
    credit: str
    description: str


def _csv_response(text: str, filename: str) -> Response:
    return Response(
        content=text,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _load_full_reports(conn, user, ids: list[UUID]) -> list[dict]:
    full = []
    for report_id in ids:
        report = reports.get_report(conn, user, report_id)
        store = db.fetch_one(conn, "select qb_location from stores where id = %s", [report["store_id"]])
        report["qb_location"] = store["qb_location"]
        full.append(report)
    return full


@router.get("/journal-entry/{report_id}", response_model=list[PreviewLine])
def preview_journal_entry(report_id: UUID, user: CurrentUser = Depends(owner_only)):
    with db.transaction() as conn:
        report = reports.get_report(conn, user, report_id)
        accounts = load_settings(conn).qb_accounts.model_dump()
    return [
        PreviewLine(account=l.account, debit=f"{l.debit:.2f}", credit=f"{l.credit:.2f}", description=l.description)
        for l in journal_entry.build_lines(report, accounts)
    ]


@router.post("/quickbooks")
def export_quickbooks(data: ExportRequest, user: CurrentUser = Depends(owner_only)):
    """Approved days in the range -> one CSV. Those days are marked 'exported'."""
    statuses = "approved,exported" if data.include_already_exported else "approved"
    with db.transaction() as conn:
        rows = reports.list_reports(
            conn, user, store_id=data.store_id, status=statuses,
            date_from=data.date_from, date_to=data.date_to, limit=5000,
        )
        if not rows:
            raise bad_request("No approved days in that range")
        full = _load_full_reports(conn, user, [r["id"] for r in rows])
        accounts = load_settings(conn).qb_accounts.model_dump()
        text = journal_entry.to_csv(full, accounts)
        for r in rows:
            db.execute(
                conn,
                "update daily_reports set status = 'exported', exported_at = now() where id = %s",
                [r["id"]],
            )
            db.execute(
                conn,
                "insert into audit_log (report_id, actor_id, action) values (%s, %s, 'exported')",
                [r["id"], user.id],
            )
    return _csv_response(text, f"quickbooks-journal-{data.date_from}-to-{data.date_to}.csv")


@router.get("/check-paid-outs.csv")
def export_check_paid_outs(date_from: date, date_to: date, user: CurrentUser = Depends(owner_only)):
    """Check paid-outs to enter in QuickBooks as checks (they're not in the journal entry)."""
    with db.transaction() as conn:
        rows = db.fetch_all(
            conn,
            """select r.business_date, s.name as store, p.check_no, p.payee, p.amount
               from paid_outs p join daily_reports r on r.id = p.report_id join stores s on s.id = r.store_id
               where p.kind = 'check' and r.status in ('approved', 'exported')
                 and r.business_date between %s and %s
               order by r.business_date, s.name, p.position""",
            [date_from, date_to],
        )
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["Date", "Store", "Check No.", "Payee", "Amount"])
    for r in rows:
        writer.writerow([f"{r['business_date']:%m/%d/%Y}", r["store"], r["check_no"] or "", r["payee"], f"{r['amount']:.2f}"])
    return _csv_response(out.getvalue(), f"check-paid-outs-{date_from}-to-{date_to}.csv")


@router.get("/raw.csv")
def export_raw(date_from: date, date_to: date, user: CurrentUser = Depends(owner_only)):
    """Every worksheet in the range, one row per day, for Excel."""
    columns = [
        "business_date", "store_name", "status", "fuel_sale", "merch_sale", "taxable_sale", "nontaxable_sale", "sales_tax", "total_sales", "gallons",
        "credit", "debit", "ebt", "total_non_cash", "cash_paid_out", "expected_cash", "cash_drop", "over_short",
        "submitted_by_name", "employee_note", "review_note",
    ]
    with db.transaction() as conn:
        rows = db.fetch_all(
            conn,
            reports.REPORT_SELECT + " where r.business_date between %s and %s order by r.business_date, s.name",
            [date_from, date_to],
        )
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(columns + ["ending_inventory"])
    for r in rows:
        tanks = "; ".join(f"{t['tank']}: {t['gallons']}" for t in (r.get("tank_inventory") or []))
        writer.writerow(["" if r[c] is None else r[c] for c in columns] + [tanks])
    return _csv_response(out.getvalue(), f"daily-sales-{date_from}-to-{date_to}.csv")
