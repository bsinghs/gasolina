"""People (the invite list). Owner only. Adding someone here is what lets them sign in."""

from uuid import UUID

from fastapi import APIRouter, Depends
from psycopg import Connection
from psycopg.errors import UniqueViolation

from app.core import db
from app.core.auth import CurrentUser, owner_only
from app.core.errors import bad_request, conflict, not_found
from app.modules.people.schemas import Person, PersonIn

router = APIRouter(prefix="/people", tags=["people"])

PERSON_SELECT = """
    select p.id, p.email, p.name, p.role, p.active, p.auth_user_id is not null as has_signed_in,
           coalesce(array_agg(m.store_id) filter (where m.store_id is not null), '{}') as store_ids
    from people p left join store_members m on m.person_id = p.id
"""


@router.get("", response_model=list[Person])
def list_people(_: CurrentUser = Depends(owner_only)):
    with db.transaction() as conn:
        return db.fetch_all(conn, PERSON_SELECT + " group by p.id order by p.active desc, p.name")


@router.post("", response_model=Person)
def invite_person(data: PersonIn, _: CurrentUser = Depends(owner_only)):
    try:
        with db.transaction() as conn:
            row = db.fetch_one(
                conn,
                "insert into people (email, name, role, active) values (%s, %s, %s, %s) returning id",
                [data.email, data.name, data.role, data.active],
            )
            _set_stores(conn, row["id"], data.store_ids)
            return _get(conn, row["id"])
    except UniqueViolation:
        raise conflict("Someone with that email is already on the list")


@router.patch("/{person_id}", response_model=Person)
def update_person(person_id: UUID, data: PersonIn, user: CurrentUser = Depends(owner_only)):
    if person_id == user.id and (data.role != "owner" or not data.active):
        raise bad_request("You can't remove your own owner access")
    with db.transaction() as conn:
        row = db.fetch_one(
            conn,
            "update people set email = %s, name = %s, role = %s, active = %s where id = %s returning id",
            [data.email, data.name, data.role, data.active, person_id],
        )
        if row is None:
            raise not_found("Person not found")
        _set_stores(conn, person_id, data.store_ids)
        return _get(conn, person_id)


def _set_stores(conn: Connection, person_id: UUID, store_ids: list[UUID]) -> None:
    db.execute(conn, "delete from store_members where person_id = %s", [person_id])
    for store_id in store_ids:
        db.execute(conn, "insert into store_members (person_id, store_id) values (%s, %s)", [person_id, store_id])


def _get(conn: Connection, person_id: UUID) -> dict:
    return db.fetch_one(conn, PERSON_SELECT + " where p.id = %s group by p.id", [person_id])
