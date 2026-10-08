"""Profit & Loss and Balance Sheet math, worked by hand (no database)."""

from decimal import Decimal as D

from app.modules.books.math import Entry, PaidOut, balance_sheet, profit_and_loss, vendor_key

VENDORS = {"sunoco fuel": "fuel", "pepsi": "merchandise", "ice co": "expense"}

ENTRIES = [
    Entry("fuel_purchase", "Load 10/3", D("20000.00"), "Sunoco Fuel"),
    Entry("merchandise_purchase", "McLane order", D("3100.55"), None),
    Entry("expense", "Payroll", D("4200.00")),
    Entry("expense", "payroll ", D("300.00")),          # same expense, different spelling → one line
    Entry("expense", "Rent", D("2500.00")),
]
PAID_OUTS = [
    PaidOut("Pepsi", D("312.00")),
    PaidOut(" PEPSI ", D("100.00")),                    # matched to the same vendor
    PaidOut("Ice Co", D("40.00")),
    PaidOut("Joe's Plumbing", D("85.50")),              # not on the list
]


def pnl(**overrides):
    args = dict(fuel_sales="30000.00", merchandise_sales="9000.00", sales_tax="180.00", taxable="3000.00",
                non_taxable="6000.00", over_short="-12.25", entries=ENTRIES, paid_outs=PAID_OUTS,
                vendor_kinds=VENDORS, count_paid_outs=True)
    return profit_and_loss(**(args | overrides))


def test_vendor_names_match_ignoring_case_and_spaces():
    assert vendor_key("  Sunoco   FUEL ") == "sunoco fuel"
    assert vendor_key(None) == ""


def test_profit_and_loss_worked_example():
    p = pnl()
    assert p.revenue == D("39000.00")                                     # 30,000 fuel + 9,000 merch; tax not revenue
    assert p.cost_of_goods == D("23512.55")                               # 20,000 + 3,100.55 + Pepsi 412
    assert p.gross_profit == D("15487.45")
    assert p.expenses == D("7125.50")                                     # 4,500 payroll + 2,500 rent + 40 ice + 85.50 unknown
    assert p.net_profit == D("8349.70")                                   # 15,487.45 − 7,125.50 − 12.25 short
    assert [(l.label, l.amount) for l in p.cost_lines] == [
        ("Fuel purchases", D("20000.00")), ("Merchandise purchases", D("3100.55")), ("Paid outs: merchandise vendors", D("412.00"))]
    assert [(l.label, l.amount) for l in p.expense_lines] == [
        ("Payroll", D("4500.00")), ("Rent", D("2500.00")), ("Paid outs: Ice Co", D("40.00")),
        ("Paid outs: vendors not on the list", D("85.50"))]
    assert p.expense_lines[-1].items == [{"vendor": "Joe's Plumbing", "amount": D("85.50")}]
    assert p.cost_lines[-1].items == [{"vendor": "Pepsi", "amount": D("412.00")}]


def test_paid_outs_can_be_left_out_so_nothing_counts_twice():
    p = pnl(count_paid_outs=False)
    assert p.cost_of_goods == D("23100.55") and p.expenses == D("7000.00")
    assert p.net_profit == D("39000.00") - D("23100.55") - D("7000.00") - D("12.25")


def test_overage_raises_profit_and_empty_month_is_zero():
    assert pnl(over_short="5.00").net_profit == pnl(over_short="0").net_profit + D("5.00")
    empty = profit_and_loss(fuel_sales=0, merchandise_sales=0, sales_tax=0, taxable=0, non_taxable=0, over_short=0,
                            entries=[], paid_outs=[], vendor_kinds={})
    assert (empty.revenue, empty.cost_of_goods, empty.expenses, empty.net_profit) == (D("0.00"),) * 4
    assert empty.cost_lines == [] and empty.expense_lines == []


def test_amounts_round_to_the_cent():
    p = profit_and_loss(fuel_sales="0.005", merchandise_sales="0", sales_tax=0, taxable=0, non_taxable=0, over_short=0,
                        entries=[Entry("expense", "Fee", D("0.004"))], paid_outs=[], vendor_kinds={})
    assert p.revenue == D("0.01") and p.expenses == D("0.00") and p.net_profit == D("0.01")


def test_balance_sheet_balances_and_shows_the_difference():
    lines = [("asset", "Cash in bank", D("25000.00")), ("asset", "Fuel inventory", D("8000.00")),
             ("liability", "Accounts payable", D("4000.00")),
             ("equity", "Owner's investment", D("20000.00")), ("equity", "Owner draws", D("-1000.00"))]
    b = balance_sheet(lines=lines, tax_collected="500.00", profit_to_date="9500.00", month_label="October 2026")
    assert (b.total_assets, b.total_liabilities, b.total_equity) == (D("33000.00"), D("4500.00"), D("28500.00"))
    assert b.difference == D("0.00") and b.balanced
    assert b.liabilities[-1].label == "PA sales tax collected in October 2026 (owed)" and b.liabilities[-1].source == "auto"
    assert b.equity[-1].label.startswith("Profit to date")

    off = balance_sheet(lines=lines, tax_collected="500.00", profit_to_date="9000.00", month_label="October 2026")
    assert off.difference == D("500.00") and not off.balanced


def test_balance_sheet_without_tax_has_no_tax_line():
    b = balance_sheet(lines=[], tax_collected="0", profit_to_date="0", month_label="May 2026")
    assert b.liabilities == [] and b.balanced and len(b.equity) == 1
