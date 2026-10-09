import re
from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

Category = Literal["fuel_purchase", "merchandise_purchase", "expense"]
Section = Literal["asset", "liability", "equity"]
MONTH = re.compile(r"(20\d{2})-(0[1-9]|1[0-2])")   # 2000-01 … 2099-12


def check_delivery(category: str, store_id, entry_date, tank, gallons) -> None:
    """Gallons only on a fuel purchase, and then the store, date and tank are needed (for Inventory)."""
    if gallons is None and tank is None:
        return
    if category != "fuel_purchase":
        raise ValueError("Gallons and tank are only for fuel purchases")
    if gallons is None or tank is None or store_id is None or entry_date is None:
        raise ValueError("A fuel delivery needs the store, date, tank and gallons")


def check_month(v: str) -> str:
    if not MONTH.fullmatch(v):
        raise ValueError("Month must look like 2026-10")
    return v


class EntryIn(BaseModel):
    """A purchase or expense the owner types in for a month.
    A fuel delivery is a fuel purchase with a date, a tank and gallons (Inventory page)."""
    month: str | None = None                      # 2026-10; may be left out when entry_date is given
    store_id: UUID | None = None                  # None = All stores (shared)
    category: Category
    description: str = Field(min_length=1, max_length=200)
    vendor_id: UUID | None = None
    amount: Decimal = Field(ge=0, decimal_places=2, max_digits=12)
    entry_date: date | None = None                # the day it was delivered / bought (optional)
    tank: str | None = Field(default=None, max_length=60)
    gallons: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=1)

    @field_validator("month")
    @classmethod
    def valid_month(cls, v: str | None) -> str | None:
        return None if v is None else check_month(v)

    @field_validator("tank")
    @classmethod
    def tidy_tank(cls, v: str | None) -> str | None:
        v = " ".join(v.split()) if v else ""
        return v or None

    @model_validator(mode="after")
    def month_and_delivery(self) -> "EntryIn":
        if self.entry_date is not None:
            if not MONTH.fullmatch(self.entry_date.strftime("%Y-%m")):
                raise ValueError("Date must be between 2000 and 2099")
            from_date = self.entry_date.strftime("%Y-%m")
            if self.month is None:
                self.month = from_date
            elif self.month != from_date:
                raise ValueError("The date must be in the entry's month")
        if self.month is None:
            raise ValueError("Give the month (or the date)")
        # Gallons / tank rules are checked by the service: on a change, after merging with what's saved
        return self

    @field_validator("description")
    @classmethod
    def tidy(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("Say what it was for")
        return v


class BalanceLineIn(BaseModel):
    section: Section
    name: str = Field(min_length=1, max_length=120)
    amount: Decimal = Field(decimal_places=2, max_digits=14)   # equity lines may be negative (owner draws)

    @field_validator("name")
    @classmethod
    def tidy(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("Give the line a name")
        return v


class BalanceIn(BaseModel):
    """All typed lines for one month (and store / shared). Replaces that month's lines."""
    month: str
    store_id: UUID | None = None
    lines: list[BalanceLineIn] = Field(default_factory=list, max_length=100)

    @field_validator("month")
    @classmethod
    def valid_month(cls, v: str) -> str:
        return check_month(v)
