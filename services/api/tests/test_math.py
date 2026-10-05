"""The worksheet math and the QuickBooks entry, using the worked example from the spec."""

from datetime import date
from decimal import Decimal

from app.modules.exports.journal_entry import build_lines, journal_number, to_csv
from app.modules.reports.reconciliation import calculate
from app.modules.settings.router import QbAccounts

EXAMPLE = dict(
    fuel_sale="4200.00", merch_sale="1350.00", sales_tax="94.50",
    credit="3100.00", debit="620.00", ebt="85.00", cash_drop="1790.00",
)
PAID_OUTS = [
    {"kind": "cash", "payee": "Ice vendor", "amount": "40.00", "gl_account": "Supplies"},
    {"kind": "check", "payee": "Beverage distributor", "amount": "312.00", "gl_account": None},
]


def test_reconciliation_matches_spec_example():
    t = calculate(**EXAMPLE, paid_outs=PAID_OUTS)
    assert t.total_sales == Decimal("5644.50")
    assert t.total_non_cash == Decimal("3805.00")
    assert t.cash_paid_out == Decimal("40.00")  # the check is not deducted
    assert t.expected_cash == Decimal("1799.50")
    assert t.over_short == Decimal("-9.50")


def _report(**overrides):
    totals = calculate(**EXAMPLE, paid_outs=PAID_OUTS)
    report = {
        **{k: Decimal(v) for k, v in EXAMPLE.items()}, "gallons": Decimal("1234.5"),
        "over_short": totals.over_short, "paid_outs": PAID_OUTS,
        "store_name": "Route 9 Fuel & Mart", "business_date": date(2026, 10, 3), "qb_location": "Route 9",
    }
    return report | overrides


def test_journal_entry_balances_when_short():
    lines = build_lines(_report(), QbAccounts().model_dump())
    assert sum(l.debit for l in lines) == sum(l.credit for l in lines) == Decimal("5644.50")
    short = [l for l in lines if l.account == "Cash Over/Short"]
    assert short[0].debit == Decimal("9.50")
    assert not any("Beverage" in l.description for l in lines)  # checks stay out


def test_journal_entry_balances_when_over():
    report = _report(cash_drop=Decimal("1800.00"), over_short=Decimal("0.50"))
    lines = build_lines(report, QbAccounts().model_dump())
    assert sum(l.debit for l in lines) == sum(l.credit for l in lines)
    assert [l.credit for l in lines if l.account == "Cash Over/Short"] == [Decimal("0.50")]


def test_csv_format():
    text = to_csv([_report()], QbAccounts().model_dump())
    rows = text.strip().splitlines()
    assert rows[0] == "Journal No.,Journal Date,Account Name,Debits,Credits,Description,Location"
    assert rows[1].startswith("ROUTE9-20261003,10/03/2026,Undeposited Funds,1790.00,,")
    assert journal_number(_report()) == "ROUTE9-20261003"


def test_taxable_and_nontaxable_add_to_total_sales():
    """Owner's worksheet (Oct 5): Subtotal = fuel + merchandise + taxable + non-taxable + tax."""
    t = calculate(**EXAMPLE, taxable_sale="210.25", nontaxable_sale="55.00", paid_outs=PAID_OUTS)
    assert t.total_sales == Decimal("5909.75")  # 5644.50 + 210.25 + 55.00
    assert t.expected_cash == Decimal("2064.75")
    assert t.over_short == Decimal("-274.75")


def test_journal_entry_credits_taxable_and_nontaxable_and_balances():
    extra = dict(taxable_sale="210.25", nontaxable_sale="55.00")
    totals = calculate(**EXAMPLE, **extra, paid_outs=PAID_OUTS)
    report = _report(**{k: Decimal(v) for k, v in extra.items()}, over_short=totals.over_short)
    lines = build_lines(report, QbAccounts().model_dump())
    assert sum(l.debit for l in lines) == sum(l.credit for l in lines) == Decimal("5909.75")
    assert [l.credit for l in lines if l.account == "Taxable Sales"] == [Decimal("210.25")]
    assert [l.credit for l in lines if l.account == "Non-Taxable Sales"] == [Decimal("55.00")]
