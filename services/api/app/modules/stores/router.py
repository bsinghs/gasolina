"""Stores (gas station locations). Everyone can list the stores they work at; only the owner edits."""

from uuid import UUID

from fastapi import APIRouter, Depends
from psycopg.errors import UniqueViolation

from app.core import db
from app.core.auth import CurrentUser, current_user, owner_only
from app.core.errors import conflict, not_found
from app.modules.stores.schemas import Store, StoreIn

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
                "insert into stores (name, qb_location, active) values (%s, %s, %s) returning *",
                [data.name, data.qb_location, data.active],
            )
    except UniqueViolation:
        raise conflict("A store with that name already exists")


@router.patch("/{store_id}", response_model=Store)
def update_store(store_id: UUID, data: StoreIn, _: CurrentUser = Depends(owner_only)):
    with db.transaction() as conn:
        row = db.fetch_one(
            conn,
            "update stores set name = %s, qb_location = %s, active = %s where id = %s returning *",
            [data.name, data.qb_location, data.active, store_id],
        )
    if row is None:
        raise not_found("Store not found")
    return row
