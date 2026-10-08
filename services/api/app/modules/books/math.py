"""The owner's books: Profit & Loss and Balance Sheet math. Pure functions, no database, easy to test.

Profit & Loss for a month:
    Revenue         = fuel sales + merchandise sales                 (PA sales tax is not revenue)
    Cost of goods   = typed fuel + merchandise purchases
                      + paid outs to fuel / merchandise vendors      (when count_paid_outs)
    Gross profit    = revenue - cost of goods
    Expenses        = typed expenses + paid outs to expense vendors
                      + paid outs to vendors not on the list        (when count_paid_outs)
    Cash over/short = sum of the days' over/short (short lowers profit, over raises it)
    Net profit      = gross profit - expenses + cash over/short

Balance Sheet at a month end:
    Assets      = typed asset lines
    Liabilities = typed liability lines + PA sales tax collected that month
    Equity      = typed equity lines + profit to date
    Difference  = assets - (liabilities + equity)      0.00 = balanced
"""

from collections import OrderedDict
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Iterable

from app.modules.reports.reconciliation import money

ZERO = Decimal("0.00")
COST_KINDS = ("fuel", "merchandise")


def vendor_key(name: str | None) -> str:
    """How paid-out names are matched to the vendor list: ignore case and extra spaces."""
    return " ".join((name or "").lower().split())


@dataclass(frozen=True)
class Entry:
    """A purchase or expense the owner typed in."""
    category: str            # fuel_purchase | merchandise_purchase | expense
    description: str
    amount: Decimal
    vendor: str | None = None


@dataclass(frozen=True)
class PaidOut:
    """A paid out from a counted daily worksheet."""
    payee: str
    amount: Decimal


@dataclass
class Line:
    label: str
    amount: Decimal
    source: str                                   # typed | paid_outs | days | auto
    items: list[dict] = field(default_factory=list)   # what's behind the line (for "tap to see")


@dataclass
class ProfitAndLoss:
    fuel_sales: Decimal
    merchandise_sales: Decimal
    taxable: Decimal
    non_taxable: Decimal
    sales_tax: Decimal
    revenue: Decimal
    cost_lines: list[Line]
    cost_of_goods: Decimal
    gross_profit: Decimal
    expense_lines: list[Line]
    expenses: Decimal
    over_short: Decimal
    net_profit: Decimal
    count_paid_outs: bool


def _sum(values: Iterable[Decimal]) -> Decimal:
    return money(sum((money(v) for v in values), ZERO))


def profit_and_loss(
    *,
    fuel_sales,
    merchandise_sales,
    sales_tax,
    taxable,
    non_taxable,
    over_short,
    entries: list[Entry],
    paid_outs: list[PaidOut],
    vendor_kinds: dict[str, str],      # vendor_key(name) -> fuel | merchandise | expense
    count_paid_outs: bool = True,
) -> ProfitAndLoss:
    fuel_sales, merchandise_sales = money(fuel_sales), money(merchandise_sales)
    revenue = money(fuel_sales + merchandise_sales)

    # ---- cost of goods ----
    cost_lines: list[Line] = []
    for category, label in (("fuel_purchase", "Fuel purchases"), ("merchandise_purchase", "Merchandise purchases")):
        typed = [e for e in entries if e.category == category]
        if typed:
            cost_lines.append(Line(label, _sum(e.amount for e in typed), "typed",
                                   [{"what": e.description, "vendor": e.vendor, "amount": money(e.amount)} for e in typed]))

    # ---- paid outs, sorted by the vendor list ----
    by_kind: dict[str | None, "OrderedDict[str, list[Decimal]]"] = {k: OrderedDict() for k in (*COST_KINDS, "expense", None)}
    if count_paid_outs:
        for p in paid_outs:
            kind = vendor_kinds.get(vendor_key(p.payee))
            name = " ".join(p.payee.split()) or "(no name)"
            # group spellings of the same vendor together under the first spelling seen
            group = next((n for n in by_kind[kind] if vendor_key(n) == vendor_key(name)), name)
            by_kind[kind].setdefault(group, []).append(money(p.amount))
    for kind, label in (("fuel", "Paid outs: fuel vendors"), ("merchandise", "Paid outs: merchandise vendors")):
        if by_kind[kind]:
            cost_lines.append(Line(label, _sum(a for v in by_kind[kind].values() for a in v), "paid_outs",
                                   [{"vendor": n, "amount": _sum(a)} for n, a in by_kind[kind].items()]))
    cost_of_goods = _sum(line.amount for line in cost_lines)

    # ---- expenses: typed (grouped by what it is) + paid outs (by vendor) ----
    expense_lines: list[Line] = []
    typed_expenses: "OrderedDict[str, list[Entry]]" = OrderedDict()
    for e in entries:
        if e.category == "expense":
            label = " ".join(e.description.split()) or "Other expense"
            group = next((k for k in typed_expenses if k.lower() == label.lower()), label)
            typed_expenses.setdefault(group, []).append(e)
    for label, items in typed_expenses.items():
        expense_lines.append(Line(label, _sum(e.amount for e in items), "typed",
                                  [{"what": e.description, "vendor": e.vendor, "amount": money(e.amount)} for e in items]))
    for name, amounts in by_kind["expense"].items():
        expense_lines.append(Line(f"Paid outs: {name}", _sum(amounts), "paid_outs", [{"vendor": name, "amount": _sum(amounts)}]))
    if by_kind[None]:
        expense_lines.append(Line("Paid outs: vendors not on the list", _sum(a for v in by_kind[None].values() for a in v), "paid_outs",
                                  [{"vendor": n, "amount": _sum(a)} for n, a in by_kind[None].items()]))
    expenses = _sum(line.amount for line in expense_lines)

    gross_profit = money(revenue - cost_of_goods)
    over_short = money(over_short)
    return ProfitAndLoss(
        fuel_sales=fuel_sales, merchandise_sales=merchandise_sales, taxable=money(taxable), non_taxable=money(non_taxable),
        sales_tax=money(sales_tax), revenue=revenue, cost_lines=cost_lines, cost_of_goods=cost_of_goods,
        gross_profit=gross_profit, expense_lines=expense_lines, expenses=expenses, over_short=over_short,
        net_profit=money(gross_profit - expenses + over_short), count_paid_outs=count_paid_outs,
    )


@dataclass
class BalanceSheet:
    assets: list[Line]
    liabilities: list[Line]
    equity: list[Line]
    total_assets: Decimal
    total_liabilities: Decimal
    total_equity: Decimal
    difference: Decimal            # assets - (liabilities + equity)
    balanced: bool


def balance_sheet(*, lines: list[tuple[str, str, Decimal]], tax_collected, profit_to_date, month_label: str) -> BalanceSheet:
    """lines = (section, name, amount) typed by the owner; section = asset | liability | equity."""
    def typed(section: str) -> list[Line]:
        return [Line(name, money(amount), "typed") for s, name, amount in lines if s == section]

    assets = typed("asset")
    liabilities = typed("liability")
    if money(tax_collected) != ZERO:
        liabilities.append(Line(f"PA sales tax collected in {month_label} (owed)", money(tax_collected), "auto"))
    equity = typed("equity") + [Line("Profit to date (from Profit & Loss)", money(profit_to_date), "auto")]
    ta, tl, te = (_sum(x.amount for x in group) for group in (assets, liabilities, equity))
    difference = money(ta - (tl + te))
    return BalanceSheet(assets, liabilities, equity, ta, tl, te, difference, difference == ZERO)
