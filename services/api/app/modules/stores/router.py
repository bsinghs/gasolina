"""Stores (gas station locations). Everyone can list the stores they work at; only the owner edits."""

import json
from uuid import UUID

from fastapi import APIRouter, Depends
from psycopg.errors import UniqueViolation

from app.core import db
from app.core.auth import CurrentUser, current_user, owner_only
from app.core.errors import conflict, not_found
from app.modules.stores.schemas import DEFAULT_TANKS, Store, StoreIn

router = APIRouter(prefix="/stores", tags=["stores"])


@router.get("", response_model=list[Store])
def list_stores(user: CurrentUser = Depends(current_user)):
    with db.transaction() as conn:
        if user.is_owner:
            return db.fetch_all(conn, "select * from stores order by name")
        return db.fetch_all(
            conn, "select * from stores where id = any(%s) and active order by name", [user.store_ids]
        )


@router.post("", response_model=Store)
def create_store(data: StoreIn, _: CurrentUser = Depends(owner_only)):
    try:
        with db.transaction() as conn:
            return db.fetch_one(
                conn,
                "insert into stores (name, qb_location, active, tanks) values (%s, %s, %s, %s) returning *",
                [data.name, data.qb_location, data.active, json.dumps(data.tanks or DEFAULT_TANKS)],
            )
    except UniqueViolation:
        raise conflict("A store with that name already exists")


@router.patch("/{store_id}", response_model=Store)
def update_store(store_id: UUID, data: StoreIn, _: CurrentUser = Depends(owner_only)):
    with db.transaction() as conn:
        row = db.fetch_one(
            conn,
            """update stores set name = %s, qb_location = %s, active = %s, tanks = coalesce(%s::jsonb, tanks)
               where id = %s returning *""",
            [data.name, data.qb_location, data.active, json.dumps(data.tanks) if data.tanks else None, store_id],
        )
    if row is None:
        raise not_found("Store not found")
    return row


@router.delete("/{store_id}")
def delete_store(store_id: UUID, _: CurrentUser = Depends(owner_only)):
    """Only for stores added by mistake. A store with worksheets must be deactivated instead."""
    with db.transaction() as conn:
        if db.fetch_one(conn, "select 1 from stores where id = %s", [store_id]) is None:
            raise not_found("Store not found")
        if db.fetch_one(conn, "select 1 from daily_reports where store_id = %s limit 1", [store_id]):
            raise conflict("This store has worksheets. Deactivate it instead so the records stay.")
        stranded = db.fetch_all(
            conn,
            """select p.name from people p join store_members m on m.person_id = p.id
               where m.store_id = %s and p.active and p.role in ('employee', 'manager')
                 and not exists (select 1 from store_members o where o.person_id = p.id and o.store_id <> %s)
               order by p.name""",
            [store_id, store_id],
        )
        if stranded:
            names = ", ".join(r["name"] for r in stranded)
            raise conflict(f"{names} only work(s) at this store. Give them another store (or remove them) first.")
        db.execute(conn, "delete from stores where id = %s", [store_id])  # store_members cascade
    return {"ok": True}
