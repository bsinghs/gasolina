"""Shapes of the data the reports API accepts and returns."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

Money = Decimal  # always 2 decimals; validated with ge=0 where it matters
Status = Literal["draft", "submitted", "returned", "approved", "exported"]
Source = Literal["typed", "ai", "ai_corrected"]


class PaidOutIn(BaseModel):
    kind: Literal["cash", "check"]
    check_no: str | None = None
    payee: str = Field(min_length=1, max_length=200)
    amount: Money = Field(ge=0, decimal_places=2, max_digits=12)
    gl_account: str | None = None


class PaidOut(PaidOutIn):
    id: UUID


class WorksheetIn(BaseModel):
    """What the employee's form sends when saving a draft."""

    store_id: UUID
    business_date: date
    fuel_sale: Money = Field(default=Decimal("0"), ge=0, decimal_places=2, max_digits=12)
    merch_sale: Money = Field(default=Decimal("0"), ge=0, decimal_places=2, max_digits=12)
    sales_tax: Money = Field(default=Decimal("0"), ge=0, decimal_places=2, max_digits=12)
    gallons: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=1, max_digits=10)
    credit: Money = Field(default=Decimal("0"), ge=0, decimal_places=2, max_digits=12)
    debit: Money = Field(default=Decimal("0"), ge=0, decimal_places=2, max_digits=12)
    ebt: Money = Field(default=Decimal("0"), ge=0, decimal_places=2, max_digits=12)
    cash_drop: Money = Field(default=Decimal("0"), ge=0, decimal_places=2, max_digits=12)
    employee_note: str | None = Field(default=None, max_length=2000)
    paid_outs: list[PaidOutIn] = Field(default_factory=list, max_length=100)
    field_sources: dict[str, Source] = Field(default_factory=dict)


class ReturnIn(BaseModel):
    note: str = Field(min_length=1, max_length=2000)


class ApproveIn(BaseModel):
    """Owner can set the expense account for each cash paid-out while approving."""

    gl_accounts: dict[UUID, str] = Field(default_factory=dict)


class AuditEntry(BaseModel):
    action: str
    actor_name: str | None
    details: dict
    at: datetime


class Report(BaseModel):
    id: UUID
    store_id: UUID
    store_name: str
    business_date: date
    status: Status
    fuel_sale: Money
    merch_sale: Money
    sales_tax: Money
    taxable_sale: Money  # calculated: sales tax / rate
    nontaxable_sale: Money  # calculated: merchandise - taxable
    gallons: Decimal
    credit: Money
    debit: Money
    ebt: Money
    cash_drop: Money
    employee_note: str | None
    total_sales: Money
    total_non_cash: Money
    cash_paid_out: Money
    expected_cash: Money
    over_short: Money
    field_sources: dict
    submitted_by_name: str | None
    submitted_at: datetime | None
    reviewed_by_name: str | None
    reviewed_at: datetime | None
    review_note: str | None
    exported_at: datetime | None
    updated_at: datetime
    paid_outs: list[PaidOut] = []
    history: list[AuditEntry] = []


class ReportSummary(BaseModel):
    """One row in a list (no line items or history)."""

    id: UUID
    store_id: UUID
    store_name: str
    business_date: date
    status: Status
    total_sales: Money
    expected_cash: Money
    over_short: Money
    submitted_by_name: str | None
    submitted_at: datetime | None
    review_note: str | None
    has_ai_values: bool
