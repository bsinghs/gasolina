"""People (the invite list). Owner only. Adding someone here is what lets them sign in.
App admins (role 'admin', from ADMIN_EMAILS) are hidden from owners and can't be changed here."""

from uuid import UUID

from fastapi import APIRouter, Depends
from psycopg import Connection
from psycopg.errors import UniqueViolation

from app.core import db
from app.core.auth import CurrentUser, owner_only
from app.core.errors import bad_request, conflict, forbidden, not_found
from app.modules.people.schemas import Person, PersonIn

router = APIRouter(prefix="/people", tags=["people"])

PERSON_SELECT = """
    select p.id, p.email, p.name, p.role, p.active, p.auth_user_id is not null as has_signed_in,
           coalesce(array_agg(m.store_id) filter (where m.store_id is not null), '{}') as store_ids
    from people p left join store_members m on m.person_id = p.id
"""


@router.get("", response_model=list[Person])
def list_people(user: CurrentUser = Depends(owner_only)):
    # App admins (support) only see each other here; the business owner sees their own team.
    hide_admins = "" if user.is_admin else " where p.role <> 'admin'"
    with db.transaction() as conn:
        return db.fetch_all(conn, PERSON_SELECT + hide_admins + " group by p.id order by p.active desc, p.name")


@router.post("", response_model=Person)
def invite_person(data: PersonIn, _: CurrentUser = Depends(owner_only)):
    _check_stores(data)
    try:
        with db.transaction() as conn:
            _check_active_stores(conn, data.store_ids, already=[])
            row = db.fetch_one(
                conn,
                "insert into people (email, name, role, active) values (%s, %s, %s, %s) returning id",
                [data.email, _name_or_placeholder(data), data.role, data.active],
            )
            _set_stores(conn, row["id"], data.store_ids)
            return _get(conn, row["id"])
    except UniqueViolation:
        raise conflict("Someone with that email is already on the list")


@router.patch("/{person_id}", response_model=Person)
def update_person(person_id: UUID, data: PersonIn, user: CurrentUser = Depends(owner_only)):
    if person_id == user.id and (data.role != "owner" or not data.active):
        raise bad_request("You can't remove your own owner access")
    _check_stores(data)
    try:
        return _update_person(person_id, data)
    except UniqueViolation:
        raise conflict("Someone with that email is already on the list")


def _update_person(person_id: UUID, data: PersonIn) -> dict:
    with db.transaction() as conn:
        target = db.fetch_one(conn, "select role from people where id = %s", [person_id])
        if target and target["role"] == "admin":
            raise forbidden("The app admin can't be changed here")
        current = db.fetch_all(conn, "select store_id from store_members where person_id = %s", [person_id])
        _check_active_stores(conn, data.store_ids, already=[r["store_id"] for r in current])
        row = db.fetch_one(
            conn,
            "update people set email = %s, name = %s, role = %s, active = %s where id = %s returning id",
            [data.email, _name_or_placeholder(data), data.role, data.active, person_id],
        )
        if row is None:
            raise not_found("Person not found")
        _set_stores(conn, person_id, data.store_ids)
        return _get(conn, person_id)


def _check_active_stores(conn: Connection, store_ids: list[UUID], already: list[UUID]) -> None:
    """A deactivated store can't be newly given to someone (keeping an existing one is fine)."""
    new = [s for s in store_ids if s not in already]
    if not new:
        return
    rows = db.fetch_all(conn, "select id, name, active from stores where id = any(%s)", [new])
    if len(rows) != len(set(new)):
        raise bad_request("One of the stores doesn't exist")
    inactive = [r["name"] for r in rows if not r["active"]]
    if inactive:
        raise bad_request(f"{', '.join(inactive)} is deactivated. Reactivate it in Settings first")


def _check_stores(data: PersonIn) -> None:
    """Employees and managers only see their stores, so they need at least one."""
    if data.role != "owner" and data.active and not data.store_ids:
        raise bad_request("Pick at least one store for this person (owners see all stores)")


def _name_or_placeholder(data: PersonIn) -> str:
    """Blank name -> the email's first part, which sign-in replaces with their Google name."""
    return data.name.strip() or data.email.split("@")[0]


def _set_stores(conn: Connection, person_id: UUID, store_ids: list[UUID]) -> None:
    db.execute(conn, "delete from store_members where person_id = %s", [person_id])
    for store_id in store_ids:
        db.execute(conn, "insert into store_members (person_id, store_id) values (%s, %s)", [person_id, store_id])


def _get(conn: Connection, person_id: UUID) -> dict:
    return db.fetch_one(conn, PERSON_SELECT + " where p.id = %s group by p.id", [person_id])


@router.delete("/{person_id}")
def delete_person(person_id: UUID, user: CurrentUser = Depends(owner_only)):
    """Only for people added by mistake. Anyone with history must be deactivated instead."""
    if person_id == user.id:
        raise bad_request("You can't delete yourself")
    with db.transaction() as conn:
        target = db.fetch_one(conn, "select role from people where id = %s", [person_id])
        if target is None:
            raise not_found("Person not found")
        if target["role"] == "admin":
            raise forbidden("The app admin can't be changed here")
        used = db.fetch_one(
            conn,
            """select 1 where exists (select 1 from daily_reports
                                      where %(p)s in (created_by, submitted_by, reviewed_by))
                          or exists (select 1 from audit_log where actor_id = %(p)s)
                          or exists (select 1 from attachments where uploaded_by = %(p)s)""",
            {"p": person_id},
        )
        if used:
            raise conflict("This person has worksheets or history. Deactivate them instead so the records stay.")
        db.execute(conn, "delete from people where id = %s", [person_id])  # store_members cascade
    return {"ok": True}
