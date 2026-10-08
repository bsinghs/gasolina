"""Month / quarter / year totals for the owner. READ-ONLY: only `select ... sum(...)` over worksheets
already saved, so nothing here can change or lose data. Money is summed in SQL as numeric (exact cents).

Which days count:
    include="approved" (default)  approved + exported days only (the owner has checked them)
    include="submitted"           also days submitted and waiting for review (shown as such)
Drafts and days sent back are never counted.
"""

import calendar
import re
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from psycopg import Connection

from app.core import db
from app.core.errors import bad_request

STATUSES = {"approved": ["approved", "exported"], "submitted": ["approved", "exported", "submitted"]}

# Every summed column: (name in the response, SQL expression)
SUMS = [
    ("fuel_sale", "sum(r.fuel_sale)"), ("merch_sale", "sum(r.merch_sale)"),
    ("taxable_sale", "sum(r.taxable_sale)"), ("nontaxable_sale", "sum(r.nontaxable_sale)"),
    ("sales_tax", "sum(r.sales_tax)"), ("total_sales", "sum(r.total_sales)"), ("gallons", "sum(r.gallons)"),
    ("credit", "sum(r.credit)"), ("debit", "sum(r.debit)"), ("ebt", "sum(r.ebt)"),
    ("total_non_cash", "sum(r.total_non_cash)"), ("cash_paid_out", "sum(r.cash_paid_out)"),
    ("expected_cash", "sum(r.expected_cash)"), ("cash_drop", "sum(r.cash_drop)"), ("over_short", "sum(r.over_short)"),
]
SUM_SQL = ", ".join(f"coalesce({expr}, 0) as {name}" for name, expr in SUMS)
COUNT_SQL = "count(*) as days, count(*) filter (where r.over_short < 0) as days_short, count(*) filter (where r.status = 'submitted') as days_unreviewed"


def period_range(period: str, value: str) -> tuple[date, date, str]:
    """'month' 2026-10 · 'quarter' 2026-Q4 · 'year' 2026 → first day, last day, label. Years 2000-2099."""
    if not re.match(r"20\d{2}", value):
        raise bad_request("Pick a year between 2000 and 2099")
    if period == "month" and re.fullmatch(r"\d{4}-\d{2}", value):
        y, m = map(int, value.split("-"))
        if 1 <= m <= 12:
            return date(y, m, 1), date(y, m, calendar.monthrange(y, m)[1]), date(y, m, 1).strftime("%B %Y")
    if period == "quarter" and re.fullmatch(r"\d{4}-Q[1-4]", value):
        y, q = int(value[:4]), int(value[-1])
        first = date(y, 3 * q - 2, 1)
        last_month = 3 * q
        return first, date(y, last_month, calendar.monthrange(y, last_month)[1]), f"Q{q} {y} ({first:%b}–{date(y, last_month, 1):%b})"
    if period == "year" and re.fullmatch(r"\d{4}", value):
        y = int(value)
        return date(y, 1, 1), date(y, 12, 31), str(y)
    raise bad_request("Pick a month (2026-10), a quarter (2026-Q4) or a year (2026)")


def summary(conn: Connection, period: str, value: str, store_id: UUID | None, include: str, today: date) -> dict:
    if include not in STATUSES:
        raise bad_request("include must be 'approved' or 'submitted'")
    first, last, label = period_range(period, value)
    where = "r.business_date between %s and %s and r.status = any(%s)"
    params: list = [first, last, STATUSES[include]]
    if store_id:
        where += " and r.store_id = %s"
        params.append(store_id)
    base = f"from daily_reports r join stores s on s.id = r.store_id where {where}"

    totals = db.fetch_one(conn, f"select {COUNT_SQL}, {SUM_SQL} {base}", params)
    stores = db.fetch_all(conn, f"select r.store_id, s.name as store_name, {COUNT_SQL}, {SUM_SQL} {base} group by r.store_id, s.name order by s.name", params)
    if period == "month":
        # one row per day per store, with the worksheet id so the screen can open it
        rows = db.fetch_all(
            conn,
            f"""select r.id as report_id, r.business_date::text as key, r.store_id, s.name as store_name, r.status,
                       1 as days, (r.over_short < 0)::int as days_short, (r.status = 'submitted')::int as days_unreviewed,
                       {", ".join(f"r.{name} as {name}" for name, _ in SUMS)}
                {base} order by r.business_date, s.name""",
            params,
        )
    else:
        rows = db.fetch_all(
            conn,
            f"""select to_char(r.business_date, 'YYYY-MM') as key, {COUNT_SQL}, {SUM_SQL}
                {base} group by 1 order by 1""",
            params,
        )
        have = {r["key"] for r in rows}
        # list every month of the period, empty ones too, so gaps are visible
        m, months = first, []
        while m <= last:
            months.append(m.strftime("%Y-%m"))
            m = (m.replace(day=28) + timedelta(days=4)).replace(day=1)
        empty = {name: Decimal("0.00") for name, _ in SUMS} | {"days": 0, "days_short": 0, "days_unreviewed": 0}
        rows = sorted(rows + [{"key": k, **empty} for k in months if k not in have], key=lambda r: r["key"])

    return {
        "period": period, "value": value, "label": label, "date_from": first, "date_to": last, "include": include,
        "totals": totals, "stores": stores, "rows": rows, "missing": _missing(conn, first, last, store_id, today),
    }


def _missing(conn: Connection, first: date, last: date, store_id: UUID | None, today: date) -> list[dict]:
    """Past days (not today) with no worksheet at all, per active store, from the day the store started."""
    end = min(last, today - timedelta(days=1))
    if end < first:
        return []
    return db.fetch_all(
        conn,
        """select s.id as store_id, s.name as store_name, count(d)::int as days
           from stores s
           cross join lateral generate_series(
               greatest(%s::date, least(s.created_at::date, coalesce((select min(business_date) from daily_reports x where x.store_id = s.id), s.created_at::date))),
               %s::date, interval '1 day') d
           where s.active and (%s::uuid is null or s.id = %s::uuid)
             and not exists (select 1 from daily_reports r where r.store_id = s.id and r.business_date = d::date)
           group by s.id, s.name having count(d) > 0 order by s.name""",
        [first, end, store_id, store_id],
    )
