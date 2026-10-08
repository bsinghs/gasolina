"""Who am I? The web app calls this right after sign-in to decide which screens to show."""

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core import db
from app.core.auth import CurrentUser, current_user
from app.modules.settings.router import load_settings

router = APIRouter(prefix="/me", tags=["me"])


class MyStore(BaseModel):
    id: UUID
    name: str
    # First day we expect worksheets: the day the store was added, or its first worksheet if older
    # (days entered after the fact). Earlier days are never shown as "missing".
    tracking_since: date
    tanks: list[str]  # underground fuel tanks, for the ending-inventory section


class ViewAsOption(BaseModel):
    id: UUID
    name: str
    role: str


class Me(BaseModel):
    id: UUID
    email: str
    name: str
    role: str
    stores: list[MyStore]
    over_short_alert: Decimal
    sales_tax_rate: Decimal
    # Only for the app admin: who they can "view as", and who is really signed in while viewing
    view_as_options: list[ViewAsOption] | None = None
    viewed_by_name: str | None = None


@router.get("", response_model=Me)
def me(user: CurrentUser = Depends(current_user)):
    with db.transaction() as conn:
        select = """
            select s.id, s.name, s.tanks,
                   least(s.created_at::date, (select min(r.business_date) from daily_reports r where r.store_id = s.id))
                       as tracking_since
            from stores s where s.active"""
        if user.is_owner:
            stores = db.fetch_all(conn, select + " order by s.name")
        else:
            stores = db.fetch_all(conn, select + " and s.id = any(%s) order by s.name", [user.store_ids])
        settings = load_settings(conn)
        admin = user.viewed_by or (user if user.is_admin else None)
        options = None
        if admin is not None:
            options = db.fetch_all(
                conn,
                """select id, name, role from people where active and role <> 'admin'
                   order by case role when 'owner' then 0 when 'manager' then 1 else 2 end, name""",
            )
    return Me(id=user.id, email=user.email, name=user.name, role=user.role, stores=stores,
              over_short_alert=settings.over_short_alert, sales_tax_rate=settings.sales_tax_rate,
              view_as_options=options, viewed_by_name=user.viewed_by.name if user.viewed_by else None)
