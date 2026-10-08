import re
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

Category = Literal["fuel_purchase", "merchandise_purchase", "expense"]
Section = Literal["asset", "liability", "equity"]
MONTH = re.compile(r"(20\d{2})-(0[1-9]|1[0-2])")   # 2000-01 … 2099-12


def check_month(v: str) -> str:
    if not MONTH.fullmatch(v):
        raise ValueError("Month must look like 2026-10")
    return v


class EntryIn(BaseModel):
    """A purchase or expense the owner types in for a month."""
    month: str                                    # 2026-10
    store_id: UUID | None = None                  # None = All stores (shared)
    category: Category
    description: str = Field(min_length=1, max_length=200)
    vendor_id: UUID | None = None
    amount: Decimal = Field(ge=0, decimal_places=2, max_digits=12)

    @field_validator("month")
    @classmethod
    def valid_month(cls, v: str) -> str:
        return check_month(v)

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
