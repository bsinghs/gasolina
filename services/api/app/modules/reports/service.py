"""Worksheet business rules: saving, the approval workflow, and reading reports back.

Status flow:  draft -> submitted -> approved -> exported
                          |  ^
                          v  |
                        returned   (owner sends back with a note; employee fixes and resubmits)
"""

import json
from datetime import date
from uuid import UUID

from psycopg import Connection

from app.core import db
from app.core.auth import CurrentUser
from app.core.errors import bad_request, conflict, forbidden, not_found
from app.modules.reports import reconciliation
from app.modules.reports.schemas import ApproveIn, WorksheetIn
from app.modules.settings.router import load_settings

NUMBER_FIELDS = ["fuel_sale", "merch_sale", "sales_tax", "gallons", "credit", "debit", "ebt", "cash_drop"]

# Who may edit a worksheet in each status
EDITABLE_BY_STAFF = {"draft", "returned"}
EDITABLE_BY_OWNER = {"draft", "returned", "submitted"}

REPORT_SELECT = """
    select r.*, s.name as store_name,
           sp.name as submitted_by_name, rp.name as reviewed_by_name
    from daily_reports r
    join stores s on s.id = r.store_id
    left join people sp on sp.id = r.submitted_by
    left join people rp on rp.id = r.reviewed_by
"""


# ---------- reading ----------

def get_report(conn: Connection, user: CurrentUser, report_id: UUID) -> dict:
    report = db.fetch_one(conn, REPORT_SELECT + " where r.id = %s", [report_id])
    if report is None:
        raise not_found("Worksheet not found")
    if not user.can_access_store(report["store_id"]):
        raise forbidden()
    report["paid_outs"] = db.fetch_all(
        conn, "select * from paid_outs where report_id = %s order by kind, position", [report_id]
    )
    report["history"] = db.fetch_all(
        conn,
        """select a.action, a.details, a.at, p.name as actor_name
           from audit_log a left join people p on p.id = a.actor_id
           where a.report_id = %s order by a.at desc""",
        [report_id],
    )
    return report


def find_report_id(conn: Connection, store_id: UUID, business_date: date) -> UUID | None:
    row = db.fetch_one(
        conn, "select id from daily_reports where store_id = %s and business_date = %s", [store_id, business_date]
    )
    return row["id"] if row else None


def list_reports(
    conn: Connection,
    user: CurrentUser,
    *,
    store_id: UUID | None = None,
    status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    mine: bool = False,
    limit: int = 200,
) -> list[dict]:
    where, params = ["true"], []
    if not user.is_owner:
        where.append("r.store_id = any(%s)")
        params.append(user.store_ids)
    if store_id:
        where.append("r.store_id = %s")
        params.append(store_id)
    if status:
        where.append("r.status = any(%s)")
        params.append(status.split(","))
    if date_from:
        where.append("r.business_date >= %s")
        params.append(date_from)
    if date_to:
        where.append("r.business_date <= %s")
        params.append(date_to)
    if mine:
        where.append("(r.created_by = %s or r.submitted_by = %s)")
        params += [user.id, user.id]
    params.append(limit)
    rows = db.fetch_all(
        conn,
        REPORT_SELECT + f" where {' and '.join(where)} order by r.business_date desc, s.name limit %s",
        params,
    )
    for row in rows:
        row["has_ai_values"] = any(v != "typed" for v in (row["field_sources"] or {}).values())
    return rows


# ---------- saving ----------

def save_worksheet(conn: Connection, user: CurrentUser, data: WorksheetIn) -> UUID:
    """Create the day's worksheet or update the existing draft. Totals are recalculated here."""
    if not user.can_access_store(data.store_id):
        raise forbidden("You're not assigned to this store")
    store = db.fetch_one(conn, "select active from stores where id = %s", [data.store_id])
    if store is None or not store["active"]:
        raise bad_request("This store is not active")

    paid_outs = [p.model_dump() for p in data.paid_outs]
    rate = load_settings(conn).sales_tax_rate
    totals = reconciliation.calculate(
        **{k: getattr(data, k) for k in NUMBER_FIELDS if k != "gallons"}, sales_tax_rate=rate, paid_outs=paid_outs
    )
    values = {k: getattr(data, k) for k in NUMBER_FIELDS} | totals.__dict__ | {
        "employee_note": data.employee_note,
        "field_sources": json.dumps(data.field_sources),
    }

    report_id = find_report_id(conn, data.store_id, data.business_date)
    if report_id is None:
        cols = ", ".join(values)
        marks = ", ".join(["%s"] * len(values))
        row = db.fetch_one(
            conn,
            f"""insert into daily_reports (store_id, business_date, created_by, {cols})
                values (%s, %s, %s, {marks}) returning id""",
            [data.store_id, data.business_date, user.id, *values.values()],
        )
        report_id = row["id"]
        _log(conn, report_id, user, "created")
    else:
        current = db.fetch_one(conn, "select status from daily_reports where id = %s for update", [report_id])
        allowed = EDITABLE_BY_OWNER if user.is_owner else EDITABLE_BY_STAFF
        if current["status"] not in allowed:
            raise conflict(f"This day is already {current['status']} and can't be edited")
        sets = ", ".join(f"{k} = %s" for k in values)
        db.execute(
            conn,
            f"update daily_reports set {sets}, updated_at = now() where id = %s",
            [*values.values(), report_id],
        )
        _log(conn, report_id, user, "saved", {"total_sales": str(totals.total_sales), "over_short": str(totals.over_short)})

    db.execute(conn, "delete from paid_outs where report_id = %s", [report_id])
    for i, p in enumerate(paid_outs):
        db.execute(
            conn,
            """insert into paid_outs (report_id, kind, check_no, payee, amount, gl_account, position)
               values (%s, %s, %s, %s, %s, %s, %s)""",
            [report_id, p["kind"], p["check_no"], p["payee"], p["amount"], p["gl_account"], i],
        )
    return report_id


# ---------- workflow ----------

def submit(conn: Connection, user: CurrentUser, report_id: UUID) -> None:
    report = _locked(conn, user, report_id)
    if report["status"] not in ("draft", "returned"):
        raise conflict(f"This day is already {report['status']}")
    if report["total_sales"] <= 0:
        raise bad_request("Enter at least one sales amount before submitting")
    db.execute(
        conn,
        """update daily_reports set status = 'submitted', submitted_by = %s, submitted_at = now(),
           updated_at = now() where id = %s""",
        [user.id, report_id],
    )
    _log(conn, report_id, user, "submitted")


def return_to_employee(conn: Connection, user: CurrentUser, report_id: UUID, note: str) -> None:
    report = _locked(conn, user, report_id)
    if report["status"] != "submitted":
        raise conflict("Only submitted days can be sent back")
    db.execute(
        conn,
        """update daily_reports set status = 'returned', review_note = %s, reviewed_by = %s,
           reviewed_at = now(), updated_at = now() where id = %s""",
        [note, user.id, report_id],
    )
    _log(conn, report_id, user, "returned", {"note": note})


def approve(conn: Connection, user: CurrentUser, report_id: UUID, data: ApproveIn) -> None:
    report = _locked(conn, user, report_id)
    if report["status"] != "submitted":
        raise conflict("Only submitted days can be approved")
    for paid_out_id, account in data.gl_accounts.items():
        db.execute(
            conn, "update paid_outs set gl_account = %s where id = %s and report_id = %s",
            [account, paid_out_id, report_id],
        )
    db.execute(
        conn,
        """update daily_reports set status = 'approved', reviewed_by = %s, reviewed_at = now(),
           updated_at = now() where id = %s""",
        [user.id, report_id],
    )
    _log(conn, report_id, user, "approved")


def reopen(conn: Connection, user: CurrentUser, report_id: UUID) -> None:
    report = _locked(conn, user, report_id)
    if report["status"] not in ("approved", "exported"):
        raise conflict("Only approved or exported days can be reopened")
    db.execute(
        conn,
        "update daily_reports set status = 'submitted', exported_at = null, updated_at = now() where id = %s",
        [report_id],
    )
    _log(conn, report_id, user, "reopened", {"was": report["status"]})


# ---------- helpers ----------

def _locked(conn: Connection, user: CurrentUser, report_id: UUID) -> dict:
    report = db.fetch_one(conn, "select * from daily_reports where id = %s for update", [report_id])
    if report is None:
        raise not_found("Worksheet not found")
    if not user.can_access_store(report["store_id"]):
        raise forbidden()
    return report


def _log(conn: Connection, report_id: UUID, user: CurrentUser, action: str, details: dict | None = None) -> None:
    db.execute(
        conn,
        "insert into audit_log (report_id, actor_id, action, details) values (%s, %s, %s, %s)",
        [report_id, user.id, action, json.dumps(details or {})],
    )
