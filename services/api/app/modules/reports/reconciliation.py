"""The worksheet math. Pure functions, no database, so it's easy to read and test.

    Total sales    = fuel + merchandise + sales tax
    Non-cash       = credit + debit + EBT
    Cash paid out  = sum of CASH paid-out lines (checks don't leave the drawer)
    Expected cash  = total sales - non-cash - cash paid out
    Over / (short) = cash drop - expected cash
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable

CENT = Decimal("0.01")


def money(value: Decimal | float | int | str | None) -> Decimal:
    return Decimal(str(value or 0)).quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Totals:
    total_sales: Decimal
    total_non_cash: Decimal
    cash_paid_out: Decimal
    expected_cash: Decimal
    over_short: Decimal


def calculate(
    *,
    fuel_sale,
    merch_sale,
    sales_tax,
    credit,
    debit,
    ebt,
    cash_drop,
    paid_outs: Iterable[dict],
) -> Totals:
    total_sales = money(fuel_sale) + money(merch_sale) + money(sales_tax)
    total_non_cash = money(credit) + money(debit) + money(ebt)
    cash_paid_out = sum((money(p["amount"]) for p in paid_outs if p["kind"] == "cash"), Decimal("0.00"))
    expected_cash = total_sales - total_non_cash - cash_paid_out
    over_short = money(cash_drop) - expected_cash
    return Totals(
        total_sales=money(total_sales),
        total_non_cash=money(total_non_cash),
        cash_paid_out=money(cash_paid_out),
        expected_cash=money(expected_cash),
        over_short=money(over_short),
    )
