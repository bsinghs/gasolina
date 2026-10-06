"""Who am I? The web app calls this right after sign-in to decide which screens to show."""

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
        if user.is_owner:
            stores = db.fetch_all(conn, "select id, name from stores where active order by name")
        else:
            stores = db.fetch_all(
                conn, "select id, name from stores where id = any(%s) and active order by name", [user.store_ids]
            )
        settings = load_settings(conn)
    return Me(id=user.id, email=user.email, name=user.name, role=user.role, stores=stores,
              over_short_alert=settings.over_short_alert, sales_tax_rate=settings.sales_tax_rate)
