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



def test_taxable_split_comes_from_sales_tax():
    """Owner (Oct 5): taxable = PA sales tax / 6%, non-taxable = merchandise - taxable. Totals unchanged."""
    t = calculate(**EXAMPLE, paid_outs=PAID_OUTS)
    assert t.taxable_sale == Decimal("1575.00")      # 94.50 / 0.06
    assert t.nontaxable_sale == Decimal("-225.00")   # 1350.00 - 1575.00: tax too high for the merch, flagged on screen
    assert t.total_sales == Decimal("5644.50")       # fuel + merch + tax, the split doesn't add to it

    real = calculate(fuel_sale="5960.50", merch_sale="3396.60", sales_tax="71.29", credit=0, debit=0, ebt=0,
                     cash_drop=0, paid_outs=[])  # TRUTH 9, Oct 1
    assert (real.taxable_sale, real.nontaxable_sale) == (Decimal("1188.17"), Decimal("2208.43"))
    assert real.taxable_sale + real.nontaxable_sale == Decimal("3396.60")


def test_split_uses_the_rate_from_settings():
    t = calculate(**EXAMPLE, sales_tax_rate="0.07", paid_outs=PAID_OUTS)  # e.g. Allegheny County
    assert t.taxable_sale == Decimal("1350.00") and t.nontaxable_sale == Decimal("0.00")


def test_journal_entry_shows_split_on_merchandise_line_and_still_balances():
    totals = calculate(**EXAMPLE, paid_outs=PAID_OUTS)
    report = _report(taxable_sale=totals.taxable_sale, nontaxable_sale=totals.nontaxable_sale)
    lines = build_lines(report, QbAccounts().model_dump())
    assert sum(l.debit for l in lines) == sum(l.credit for l in lines) == Decimal("5644.50")
    merch = [l for l in lines if l.account == "Merchandise Sales"][0]
    assert merch.credit == Decimal("1350.00") and "taxable 1575.00" in merch.description
