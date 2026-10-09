"""Inventory for the owner: fetch tank readings, deliveries, sales and purchases; math.py does the math."""

from dataclasses import asdict
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from psycopg import Connection

from app.core import db
from app.core.errors import not_found
from app.modules.books.math import vendor_key
from app.modules.books.service import vendor_kinds
from app.modules.inventory import math
from app.modules.settings.router import load_settings
from app.modules.stores.schemas import specs_for
from app.modules.summaries.service import STATUSES, period_range

# Tank readings are measurements, so days waiting for review count too (not drafts or days sent back)
READING_STATUSES = ["submitted", "approved", "exported"]


def inventory(conn: Connection, month: str, store_id: UUID | None, include: str, today: date) -> dict:
    first, last, label = period_range("month", month)
    if store_id:
        stores = db.fetch_all(conn, "select * from stores where id = %s", [store_id])
        if not stores:
            raise not_found("Store not found")
    else:
        stores = db.fetch_all(conn, "select * from stores where active order by name")
    reorder = load_settings(conn).reorder_percent
    kinds = vendor_kinds(conn)
    as_of = min(today, last)
    return {
        "month": month, "label": label, "reorder_percent": reorder, "as_of": as_of,
        "stores": [
            {"store_id": s["id"], "store_name": s["name"],
             "fuel": _fuel(conn, s, first, last, reorder, include),
             "merchandise": asdict(_merchandise(conn, s["id"], first, last, include, kinds, as_of))}
            for s in stores
        ],
    }


# ---------- fuel ----------

def _fuel(conn: Connection, store: dict, first: date, last: date, reorder: int, include: str) -> dict:
    readings = _readings(conn, store["id"], last)
    deliveries = deliveries_for(conn, store["id"], None, last)
    specs = specs_for(store["tanks"], store["tank_specs"])
    tanks = []
    for spec in specs:
        name = spec["name"]
        names = {name, *spec["aliases"]}        # a renamed tank keeps its history under its old names
        mine = [r for r in readings if r[0] in names]
        before = max((r for r in mine if r[1].day < first), key=lambda r: r[1].day, default=None)
        tanks.append(math.tank_usage(
            name=name, grade=spec["grade"], capacity=Decimal(spec["capacity"]) if spec["capacity"] else None,
            before=before[1] if before else None, readings=[r[1] for r in mine if r[1].day >= first],
            deliveries=[d["delivery"] for d in deliveries if d["tank"] in names], first=first, last=last,
            reorder_percent=reorder,
        ))

    check = None
    window = math.common_window(tanks)
    if window:
        start = window[0] + timedelta(days=1)
        pump = db.fetch_one(
            conn,
            """select coalesce(sum(gallons), 0) as g from daily_reports
               where store_id = %s and business_date between %s and %s and status = any(%s)""",
            [store["id"], start, window[1], READING_STATUSES],
        )["g"]
        check = asdict(math.pump_check(window, start, pump, tanks))

    sold = db.fetch_one(
        conn,
        """select coalesce(sum(fuel_sale), 0) as sales, coalesce(sum(gallons), 0) as gallons from daily_reports
           where store_id = %s and business_date between %s and %s and status = any(%s)""",
        [store["id"], first, last, STATUSES[include]],
    )
    in_month = [d["delivery"] for d in deliveries if first <= d["delivery"].day <= last]
    return {
        "tanks": [asdict(t) for t in tanks],
        "grades": [asdict(g) for g in math.by_grade(tanks)],
        "pump_check": check,
        "money": asdict(math.fuel_money(sold["sales"], sold["gallons"], in_month)),
        "deliveries": [{k: v for k, v in d.items() if k != "delivery"} for d in deliveries if first <= d["entry_date"] <= last],
    }


def _readings(conn: Connection, store_id: UUID, last: date) -> list[tuple[str, math.Reading]]:
    rows = db.fetch_all(
        conn,
        """select business_date, tank_inventory from daily_reports
           where store_id = %s and business_date <= %s and status = any(%s)
             and jsonb_array_length(tank_inventory) > 0
           order by business_date""",
        [store_id, last, READING_STATUSES],
    )
    return [(t["tank"], math.Reading(r["business_date"], Decimal(str(t["gallons"]))))
            for r in rows for t in r["tank_inventory"]]


def deliveries_for(conn: Connection, store_id: UUID, first: date | None, last: date) -> list[dict]:
    """Fuel deliveries (fuel purchases with gallons) for a store, oldest first."""
    rows = db.fetch_all(
        conn,
        """select e.id, e.entry_date, e.tank, e.gallons, e.amount, e.description, e.vendor_id, v.name as vendor_name
           from ledger_entries e left join vendors v on v.id = e.vendor_id
           where e.store_id = %s and e.gallons is not null and e.entry_date <= %s
             and (%s::date is null or e.entry_date >= %s::date)
           order by e.entry_date, e.created_at""",
        [store_id, last, first, first],
    )
    for r in rows:
        r["delivery"] = math.Delivery(r["entry_date"], r["gallons"], r["amount"])
    return rows


# ---------- merchandise ----------

def _merchandise(conn: Connection, store_id: UUID, first: date, last: date, include: str,
                 kinds: dict[str, str], as_of: date) -> math.Merchandise:
    statuses = STATUSES[include]
    sold = db.fetch_one(
        conn,
        """select coalesce(sum(merch_sale), 0) as merch from daily_reports
           where store_id = %s and business_date between %s and %s and status = any(%s)""",
        [store_id, first, last, statuses],
    )["merch"]
    typed = db.fetch_all(
        conn,
        """select v.name as vendor, e.amount, e.entry_date from ledger_entries e left join vendors v on v.id = e.vendor_id
           where e.store_id = %s and e.category = 'merchandise_purchase' and e.month = %s""",
        [store_id, first],
    )
    paid = db.fetch_all(
        conn,
        """select p.payee, p.amount, r.business_date from paid_outs p join daily_reports r on r.id = p.report_id
           where r.store_id = %s and r.business_date between %s and %s and r.status = any(%s)""",
        [store_id, first, last, statuses],
    )
    purchases = [math.Purchase(t["vendor"], t["amount"], t["entry_date"], "typed") for t in typed] + \
                [math.Purchase(p["payee"], p["amount"], p["business_date"], "paid_out") for p in paid]

    # latest purchase before this month, per vendor (typed with a date, or a paid out on a counted day)
    earlier = db.fetch_all(
        conn,
        """select v.name as vendor, max(e.entry_date) as day from ledger_entries e join vendors v on v.id = e.vendor_id
           where e.store_id = %s and e.category = 'merchandise_purchase' and e.entry_date < %s group by v.name
           union all
           select p.payee, max(r.business_date) from paid_outs p join daily_reports r on r.id = p.report_id
           where r.store_id = %s and r.business_date < %s and r.status = any(%s) group by p.payee""",
        [store_id, first, store_id, first, statuses],
    )
    last_days: dict[str, date] = {}
    for e in earlier:
        key = vendor_key(e["vendor"])
        if kinds.get(key) == "merchandise" and e["day"] and (key not in last_days or e["day"] > last_days[key]):
            last_days[key] = e["day"]
    names = [v["name"] for v in db.fetch_all(
        conn, "select name from vendors where kind = 'merchandise' and active order by name")]
    return math.merchandise(sold=sold, purchases=purchases, earlier_last_days=last_days,
                            vendor_names=names, kinds=kinds, as_of=as_of)
