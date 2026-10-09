"""The owner's books: fetch rows for a month, hand them to math.py, save typed entries and balance lines.
All math is in math.py; this file only talks to the database."""

from dataclasses import asdict
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from psycopg import Connection

from app.core import audit, db
from app.core.auth import CurrentUser
from app.core.dates import business_today
from app.core.errors import bad_request, conflict, not_found
from app.modules.books import math
from app.modules.books.schemas import BalanceIn, EntryIn, check_delivery
from app.modules.summaries.service import STATUSES, period_range


# ---------- helpers ----------

def month_bounds(month: str) -> tuple[date, date, str]:
    return period_range("month", month)


def _store_clause(column: str, store_id: UUID | None) -> tuple[str, list]:
    """A store's own rows, or everything (incl. shared) for All stores."""
    return (f" and {column} = %s", [store_id]) if store_id else ("", [])


def _check_store(conn: Connection, store_id: UUID | None) -> None:
    if store_id and db.fetch_one(conn, "select 1 from stores where id = %s", [store_id]) is None:
        raise bad_request("That store doesn't exist")


def vendor_kinds(conn: Connection) -> dict[str, str]:
    return {math.vendor_key(v["name"]): v["kind"] for v in db.fetch_all(conn, "select name, kind from vendors")}


def entries(conn: Connection, first: date, last: date, store_id: UUID | None) -> list[dict]:
    clause, params = _store_clause("e.store_id", store_id)
    return db.fetch_all(
        conn,
        f"""select e.*, v.name as vendor_name, s.name as store_name
            from ledger_entries e left join vendors v on v.id = e.vendor_id left join stores s on s.id = e.store_id
            where e.month between date_trunc('month', %s::date) and %s {clause}
            order by e.month, e.category, e.created_at""",
        [first, last, *params],
    )


def paid_out_rows(conn: Connection, first: date, last: date, store_id: UUID | None, include: str) -> list[dict]:
    clause, params = _store_clause("r.store_id", store_id)
    return db.fetch_all(
        conn,
        f"""select p.payee, p.amount, p.kind, r.business_date, s.name as store_name
            from paid_outs p join daily_reports r on r.id = p.report_id join stores s on s.id = r.store_id
            where r.business_date between %s and %s and r.status = any(%s) {clause}
            order by r.business_date, p.position""",
        [first, last, STATUSES[include], *params],
    )


def _day_sums(conn: Connection, first: date, last: date, store_id: UUID | None, include: str) -> dict:
    clause, params = _store_clause("r.store_id", store_id)
    return db.fetch_one(
        conn,
        f"""select count(*) as days, coalesce(sum(fuel_sale), 0) as fuel, coalesce(sum(merch_sale), 0) as merch,
                   coalesce(sum(sales_tax), 0) as tax, coalesce(sum(taxable_sale), 0) as taxable,
                   coalesce(sum(nontaxable_sale), 0) as nontaxable, coalesce(sum(over_short), 0) as over_short
            from daily_reports r where r.business_date between %s and %s and r.status = any(%s) {clause}""",
        [first, last, STATUSES[include], *params],
    )


# ---------- Profit & Loss ----------

def profit_and_loss(conn: Connection, month: str, store_id: UUID | None, include: str, count_paid_outs: bool) -> dict:
    first, last, label = month_bounds(month)
    pnl = _pnl(conn, first, last, store_id, include, count_paid_outs, vendor_kinds(conn))
    days = _day_sums(conn, first, last, store_id, include)["days"]
    return {"month": month, "label": label, "days": days, **asdict(pnl)}


def _pnl(conn, first, last, store_id, include, count_paid_outs, kinds) -> math.ProfitAndLoss:
    s = _day_sums(conn, first, last, store_id, include)
    typed = [math.Entry(e["category"], e["description"], e["amount"], e["vendor_name"]) for e in entries(conn, first, last, store_id)]
    paid = [math.PaidOut(p["payee"], p["amount"]) for p in paid_out_rows(conn, first, last, store_id, include)]
    return math.profit_and_loss(
        fuel_sales=s["fuel"], merchandise_sales=s["merch"], sales_tax=s["tax"], taxable=s["taxable"],
        non_taxable=s["nontaxable"], over_short=s["over_short"], entries=typed, paid_outs=paid,
        vendor_kinds=kinds, count_paid_outs=count_paid_outs,
    )


def _months(first: date, last: date) -> list[tuple[date, date]]:
    out, m = [], first.replace(day=1)
    while m <= last:
        nxt = (m.replace(day=28) + timedelta(days=4)).replace(day=1)
        out.append((m, nxt - timedelta(days=1)))
        m = nxt
    return out


def profit_and_loss_year(conn: Connection, year: str, store_id: UUID | None, include: str, count_paid_outs: bool) -> dict:
    first, last, _ = period_range("year", year)
    kinds = vendor_kinds(conn)
    rows = []
    for m_first, m_last in _months(first, last):
        p = _pnl(conn, m_first, m_last, store_id, include, count_paid_outs, kinds)
        rows.append({"month": m_first.strftime("%Y-%m"), "revenue": p.revenue, "cost_of_goods": p.cost_of_goods,
                     "expenses": p.expenses, "over_short": p.over_short, "net_profit": p.net_profit})
    totals = {k: math.money(sum((r[k] for r in rows), Decimal("0"))) for k in ("revenue", "cost_of_goods", "expenses", "over_short", "net_profit")}
    return {"year": year, "months": rows, "totals": totals}


def _first_month_with_data(conn: Connection, store_id: UUID | None) -> date | None:
    clause_r, p_r = _store_clause("store_id", store_id)
    clause_e, p_e = _store_clause("store_id", store_id)
    row = db.fetch_one(
        conn,
        f"""select least((select min(business_date) from daily_reports where true {clause_r}),
                         (select min(month) from ledger_entries where true {clause_e})) as first""",
        [*p_r, *p_e],
    )
    return row["first"]


def profit_to_date(conn: Connection, last: date, store_id: UUID | None, include: str, count_paid_outs: bool = True) -> Decimal:
    """Sum of every month's net profit from the first month with data up to and including `last`."""
    start = _first_month_with_data(conn, store_id)
    if start is None or start > last:
        return Decimal("0.00")
    kinds = vendor_kinds(conn)
    return math.money(sum((_pnl(conn, a, b, store_id, include, count_paid_outs, kinds).net_profit for a, b in _months(start, last)), Decimal("0")))


# ---------- typed entries ----------

def list_entries(conn: Connection, month: str, store_id: UUID | None) -> list[dict]:
    first, last, _ = month_bounds(month)
    return entries(conn, first, last, store_id)


def _check_vendor(conn: Connection, vendor_id: UUID | None, keeps: UUID | None = None) -> None:
    """The vendor must be on the list and active (an entry being edited may keep the vendor it already has)."""
    if not vendor_id:
        return
    v = db.fetch_one(conn, "select active, name from vendors where id = %s", [vendor_id])
    if v is None:
        raise bad_request("That vendor isn't on the list")
    if not v["active"] and vendor_id != keeps:
        raise bad_request(f"{v['name']} is deactivated. Reactivate it on the Vendors tab first.")


DELIVERY_FIELDS = ("entry_date", "tank", "gallons")


def _check_tank(conn: Connection, store_id: UUID | None, tank: str | None, keeps: str | None = None) -> None:
    """A delivery goes into one of the store's tanks (an edited entry may keep a tank since renamed)."""
    if tank is None or tank == keeps:
        return
    row = db.fetch_one(conn, "select tanks from stores where id = %s", [store_id])
    if row is None or tank not in row["tanks"]:
        raise bad_request(f"{tank} isn't one of this store's tanks (Settings)")


def _check_delivery(category, store_id, entry_date, tank, gallons) -> None:
    try:
        check_delivery(category, store_id, entry_date, tank, gallons)
    except ValueError as exc:
        raise bad_request(str(exc)) from None
    if entry_date is not None and entry_date > business_today() + timedelta(days=1):
        raise bad_request("The date can't be in the future")


def add_entry(conn: Connection, user: CurrentUser, data: EntryIn) -> dict:
    _check_delivery(data.category, data.store_id, data.entry_date, data.tank, data.gallons)
    _check_store(conn, data.store_id)
    _check_vendor(conn, data.vendor_id)
    _check_tank(conn, data.store_id, data.tank)
    row = db.fetch_one(
        conn,
        """insert into ledger_entries (month, store_id, category, description, vendor_id, amount, created_by,
                                       entry_date, tank, gallons)
           values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) returning id""",
        [f"{data.month}-01", data.store_id, data.category, data.description, data.vendor_id, data.amount, user.id,
         data.entry_date, data.tank, data.gallons],
    )
    audit.log(conn, user, "ledger.added", {"id": row["id"], **data.model_dump()})
    return _entry(conn, row["id"])


def update_entry(conn: Connection, user: CurrentUser, entry_id: UUID, data: EntryIn) -> dict:
    """Change an entry. Date, tank and gallons are kept as they are when the request doesn't send them
    (the P&L screen doesn't know about deliveries), so editing there never loses them."""
    _check_store(conn, data.store_id)
    before = _entry(conn, entry_id)
    _check_vendor(conn, data.vendor_id, keeps=before["vendor_id"])
    kept = {f: (getattr(data, f) if f in data.model_fields_set else before[f]) for f in DELIVERY_FIELDS}
    if kept["entry_date"] is not None and kept["entry_date"].strftime("%Y-%m") != data.month:
        raise bad_request("The entry's date is in another month. Change the date too.")
    _check_delivery(data.category, data.store_id, kept["entry_date"], kept["tank"], kept["gallons"])
    _check_tank(conn, data.store_id, kept["tank"], keeps=before["tank"] if data.store_id == before["store_id"] else None)
    db.execute(
        conn,
        """update ledger_entries set month = %s, store_id = %s, category = %s, description = %s, vendor_id = %s,
           amount = %s, entry_date = %s, tank = %s, gallons = %s, updated_at = now() where id = %s""",
        [f"{data.month}-01", data.store_id, data.category, data.description, data.vendor_id, data.amount,
         kept["entry_date"], kept["tank"], kept["gallons"], entry_id],
    )
    audit.log(conn, user, "ledger.changed", {
        "id": entry_id,
        "before": {k: before[k] for k in ("description", "amount", "category", *DELIVERY_FIELDS)},
        "after": data.model_dump() | kept})
    return _entry(conn, entry_id)


def delete_entry(conn: Connection, user: CurrentUser, entry_id: UUID) -> None:
    before = _entry(conn, entry_id)
    db.execute(conn, "delete from ledger_entries where id = %s", [entry_id])
    # the history log keeps what was removed, so it can be typed back if deleted by mistake
    audit.log(conn, user, "ledger.deleted", {k: before[k] for k in ("id", "month", "store_id", "category", "description", "vendor_name", "amount", *DELIVERY_FIELDS)})


def _entry(conn: Connection, entry_id: UUID) -> dict:
    row = db.fetch_one(
        conn,
        """select e.*, v.name as vendor_name, s.name as store_name from ledger_entries e
           left join vendors v on v.id = e.vendor_id left join stores s on s.id = e.store_id where e.id = %s""",
        [entry_id],
    )
    if row is None:
        raise not_found("Entry not found")
    return row


# ---------- Balance Sheet ----------

def _lock_month(conn: Connection, first: date, store_id: UUID | None) -> None:
    """One save / copy at a time for a month (+ store): a double tap waits for the first one instead of
    adding the lines twice. Released when the transaction ends."""
    db.execute(conn, "select pg_advisory_xact_lock(hashtext(%s))", [f"balance:{first}:{store_id or 'shared'}"])


def _lines(conn: Connection, month_first: date, store_id: UUID | None) -> list[dict]:
    return db.fetch_all(
        conn,
        """select section, name, amount from balance_lines
           where month = %s and store_id is not distinct from %s order by position""",
        [month_first, store_id],
    )


def balance(conn: Connection, month: str, store_id: UUID | None, include: str, count_paid_outs: bool = True) -> dict:
    """One store's sheet, or (store_id None) the whole business: shared lines + every store's own lines,
    with tax and profit to date for all stores, so the group sheet adds up."""
    first, last, label = month_bounds(month)
    lines = _lines(conn, first, store_id)                    # what this view edits
    shown = [(l["section"], l["name"], l["amount"]) for l in lines]
    if store_id is None:
        shown += [(l["section"], f"{l['name']} ({l['store_name']})", l["amount"]) for l in db.fetch_all(
            conn,
            """select b.section, b.name, b.amount, s.name as store_name from balance_lines b join stores s on s.id = b.store_id
               where b.month = %s order by s.name, b.position""",
            [first],
        )]
    sheet = math.balance_sheet(
        lines=shown,
        tax_collected=_day_sums(conn, first, last, store_id, include)["tax"],
        profit_to_date=profit_to_date(conn, last, store_id, include, count_paid_outs),
        month_label=label,
    )
    return {"month": month, "label": label, "store_id": store_id, "typed_lines": lines, "count_paid_outs": count_paid_outs, **asdict(sheet)}


def save_balance(conn: Connection, user: CurrentUser, data: BalanceIn) -> None:
    _check_store(conn, data.store_id)
    first = date.fromisoformat(f"{data.month}-01")
    _lock_month(conn, first, data.store_id)
    before = _lines(conn, first, data.store_id)
    db.execute(conn, "delete from balance_lines where month = %s and store_id is not distinct from %s", [first, data.store_id])
    for i, line in enumerate(data.lines):
        db.execute(conn, "insert into balance_lines (month, store_id, section, name, amount, position) values (%s, %s, %s, %s, %s, %s)",
                   [first, data.store_id, line.section, " ".join(line.name.split()), line.amount, i])
    audit.log(conn, user, "balance.saved", {"month": data.month, "store_id": data.store_id, "before": before,
                                            "after": [l.model_dump() for l in data.lines]})


def copy_previous(conn: Connection, user: CurrentUser, month: str, store_id: UUID | None) -> int:
    """Copy the latest earlier month's lines into an EMPTY month. Never overwrites."""
    first = date.fromisoformat(f"{month}-01")
    _lock_month(conn, first, store_id)
    if _lines(conn, first, store_id):
        raise conflict("This month already has balances. Clear them first if you want to copy.")
    src = db.fetch_one(conn, "select max(month) as m from balance_lines where month < %s and store_id is not distinct from %s", [first, store_id])["m"]
    if src is None:
        raise bad_request("There's no earlier month with balances to copy")
    db.execute(
        conn,
        """insert into balance_lines (month, store_id, section, name, amount, position)
           select %s, store_id, section, name, amount, position from balance_lines
           where month = %s and store_id is not distinct from %s""",
        [first, src, store_id],
    )
    n = len(_lines(conn, first, store_id))
    audit.log(conn, user, "balance.copied", {"month": month, "from": src, "store_id": store_id, "lines": n})
    return n
