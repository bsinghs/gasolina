"""Vendor list and spending by vendor. Paid outs are matched to vendors by name (books.math.vendor_key)."""

from datetime import date
from decimal import Decimal
from uuid import UUID

from psycopg import Connection
from psycopg.errors import UniqueViolation

from app.core import audit, db
from app.core.auth import CurrentUser
from app.core.errors import conflict, not_found
from app.modules.books import service as books
from app.modules.books.math import vendor_key
from app.modules.reports.reconciliation import money
from app.modules.vendors.schemas import VendorIn

SELECT = """select v.*, exists (select 1 from ledger_entries e where e.vendor_id = v.id) as used from vendors v"""


def list_vendors(conn: Connection) -> list[dict]:
    return db.fetch_all(conn, SELECT + " order by v.active desc, lower(v.name)")


def add(conn: Connection, user: CurrentUser, data: VendorIn) -> dict:
    try:
        with conn.transaction():
            row = db.fetch_one(conn, "insert into vendors (name, kind, active) values (%s, %s, %s) returning id",
                               [data.name, data.kind, data.active])
    except UniqueViolation:
        raise conflict(f"“{data.name}” is already on the vendor list") from None
    audit.log(conn, user, "vendor.added", data.model_dump())
    return db.fetch_one(conn, SELECT + " where v.id = %s", [row["id"]])


def update(conn: Connection, user: CurrentUser, vendor_id: UUID, data: VendorIn) -> dict:
    before = db.fetch_one(conn, "select name, kind, active from vendors where id = %s", [vendor_id])
    try:
        with conn.transaction():
            row = db.fetch_one(conn, "update vendors set name = %s, kind = %s, active = %s where id = %s returning id",
                               [data.name, data.kind, data.active, vendor_id])
    except UniqueViolation:
        raise conflict(f"“{data.name}” is already on the vendor list") from None
    if row is None:
        raise not_found("Vendor not found")
    audit.log(conn, user, "vendor.changed", {"id": vendor_id, "before": before, "after": data.model_dump()})
    return db.fetch_one(conn, SELECT + " where v.id = %s", [vendor_id])


def delete(conn: Connection, user: CurrentUser, vendor_id: UUID) -> None:
    row = db.fetch_one(conn, SELECT + " where v.id = %s", [vendor_id])
    if row is None:
        raise not_found("Vendor not found")
    if row["used"]:
        raise conflict(f"{row['name']} has purchases or expenses. Deactivate it instead so they keep their vendor.")
    db.execute(conn, "delete from vendors where id = %s", [vendor_id])
    audit.log(conn, user, "vendor.deleted", {"id": vendor_id, "name": row["name"]})


def spending(conn: Connection, first: date, last: date, store_id: UUID | None, include: str) -> dict:
    """Money paid to each vendor: typed purchases/expenses + paid outs on counted days."""
    kinds = books.vendor_kinds(conn)
    names = {vendor_key(v["name"]): v["name"] for v in list_vendors(conn)}
    rows: dict[str, dict] = {}

    def add_to(name: str, column: str, amount, detail: dict) -> None:
        key = vendor_key(name)
        row = rows.setdefault(key, {"vendor": names.get(key, " ".join(name.split())), "on_list": key in names,
                                    "cost_of_goods": Decimal("0"), "expense": Decimal("0"), "not_on_list": Decimal("0"), "items": []})
        row[column] += money(amount)
        row["items"].append(detail)

    for e in books.entries(conn, first, last, store_id):
        if e["vendor_name"]:
            column = "expense" if e["category"] == "expense" else "cost_of_goods"
            add_to(e["vendor_name"], column, e["amount"], {"date": e["month"], "what": e["description"], "amount": money(e["amount"]), "source": "typed"})
    for p in books.paid_out_rows(conn, first, last, store_id, include):
        kind = kinds.get(vendor_key(p["payee"]))
        column = "not_on_list" if kind is None else ("expense" if kind == "expense" else "cost_of_goods")
        add_to(p["payee"], column, p["amount"], {"date": p["business_date"], "what": f"Paid out ({p['kind']}) at {p['store_name']}", "amount": money(p["amount"]), "source": "paid_out"})

    total = money(sum((r["cost_of_goods"] + r["expense"] + r["not_on_list"] for r in rows.values()), Decimal("0")))
    out = []
    for r in rows.values():
        r["total"] = money(r["cost_of_goods"] + r["expense"] + r["not_on_list"])
        r["share"] = (r["total"] / total * 100).quantize(Decimal("0.1")) if total else Decimal("0.0")
        out.append(r)
    out.sort(key=lambda r: (-r["total"], r["vendor"].lower()))
    return {"vendors": out, "total": total}
