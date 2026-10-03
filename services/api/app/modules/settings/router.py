"""Owner settings: QuickBooks account names and the over/short alert threshold."""

import json
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core import db
from app.core.auth import CurrentUser, owner_only

router = APIRouter(prefix="/settings", tags=["settings"])


class QbAccounts(BaseModel):
    cash: str = "Undeposited Funds"
    cards: str = "Credit Card Clearing"
    ebt: str = "EBT Receivable"
    fuel_sales: str = "Fuel Sales"
    merch_sales: str = "Merchandise Sales"
    sales_tax: str = "Sales Tax Payable"
    over_short: str = "Cash Over/Short"
    default_expense: str = "Miscellaneous Expense"


class AppSettings(BaseModel):
    over_short_alert: Decimal = Field(default=Decimal("20"), ge=0)
    qb_accounts: QbAccounts = QbAccounts()


def load_settings(conn) -> AppSettings:
    rows = db.fetch_all(conn, "select key, value from settings")
    return AppSettings(**{r["key"]: r["value"] for r in rows})


@router.get("", response_model=AppSettings)
def get_settings(_: CurrentUser = Depends(owner_only)):
    with db.transaction() as conn:
        return load_settings(conn)


@router.put("", response_model=AppSettings)
def save_settings(data: AppSettings, _: CurrentUser = Depends(owner_only)):
    with db.transaction() as conn:
        for key, value in data.model_dump(mode="json").items():
            db.execute(
                conn,
                "insert into settings (key, value) values (%s, %s) on conflict (key) do update set value = excluded.value",
                [key, json.dumps(value)],
            )
        return load_settings(conn)
