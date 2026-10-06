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


class Me(BaseModel):
    id: UUID
    email: str
    name: str
    role: str
    stores: list[MyStore]
    over_short_alert: Decimal
    sales_tax_rate: Decimal


@router.get("", response_model=Me)
def me(user: CurrentUser = Depends(current_user)):
    with db.transaction() as conn:
        select = """
            select s.id, s.name,
                   least(s.created_at::date, (select min(r.business_date) from daily_reports r where r.store_id = s.id))
                       as tracking_since
            from stores s where s.active"""
        if user.is_owner:
            stores = db.fetch_all(conn, select + " order by s.name")
        else:
            stores = db.fetch_all(conn, select + " and s.id = any(%s) order by s.name", [user.store_ids])
        settings = load_settings(conn)
    return Me(id=user.id, email=user.email, name=user.name, role=user.role, stores=stores,
              over_short_alert=settings.over_short_alert, sales_tax_rate=settings.sales_tax_rate)
