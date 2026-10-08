"""Owner reports: totals for a month, quarter or year (one store or all). Read-only."""

import csv
import io
from datetime import date
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Response

from app.core import db
from app.core.auth import CurrentUser, owner_only
from app.core.json import exact
from app.modules.summaries import service

router = APIRouter(prefix="/summaries", tags=["summaries"])


Period = Literal["month", "quarter", "year"]
Include = Literal["approved", "submitted"]


@router.get("")
def get_summary(period: Period, value: str, store_id: UUID | None = None, include: Include = "approved",
                _: CurrentUser = Depends(owner_only)):
    with db.transaction() as conn:
        return exact(service.summary(conn, period, value, store_id, include, date.today()))


CSV_COLUMNS = ["days", "fuel_sale", "merch_sale", "taxable_sale", "nontaxable_sale", "sales_tax", "total_sales",
               "gallons", "credit", "debit", "ebt", "cash_paid_out", "expected_cash", "cash_drop", "over_short", "days_short"]


@router.get("/csv")
def summary_csv(period: Period, value: str, store_id: UUID | None = None, include: Include = "approved",
                _: CurrentUser = Depends(owner_only)):
    """The same report as a spreadsheet: one line per day (month) or per month (quarter/year), then per store, then the total."""
    with db.transaction() as conn:
        s = service.summary(conn, period, value, store_id, include, date.today())
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow([f"Shift Close · {s['label']} · {'approved days' if include == 'approved' else 'approved + submitted days'}"])
    w.writerow(["date" if period == "month" else "month", "store", "status"] + CSV_COLUMNS)
    for r in s["rows"]:
        w.writerow([r["key"], r.get("store_name", "All stores"), r.get("status", "")] + [r.get(c, "") for c in CSV_COLUMNS])
    w.writerow([])
    for r in s["stores"]:
        w.writerow(["Store total", r["store_name"], ""] + [r[c] for c in CSV_COLUMNS])
    w.writerow(["Total", "", ""] + [s["totals"][c] for c in CSV_COLUMNS])
    name = f"shift-close-{s['value']}{'-store' if store_id else ''}.csv"
    return Response(out.getvalue(), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{name}"'})
