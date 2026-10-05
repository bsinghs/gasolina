"""Turns one approved worksheet into a balanced QuickBooks journal entry.

    Debits:  cash drop -> Undeposited Funds, credit+debit -> Card Clearing, EBT -> EBT Receivable,
             each cash paid-out -> its expense account, a shortage -> Cash Over/Short
    Credits: fuel sales, merchandise sales, taxable sales, non-taxable sales, sales tax, an overage -> Cash Over/Short

The over/short line is exactly the gap between the drawer and the sales, so debits always equal credits.
Check paid-outs are NOT in here: they're paid from the bank, not the drawer.
"""

import csv
import io
import re
from dataclasses import dataclass
from decimal import Decimal

from app.modules.reports.reconciliation import money


@dataclass
class Line:
    account: str
    debit: Decimal
    credit: Decimal
    description: str


def build_lines(report: dict, accounts: dict) -> list[Line]:
    lines: list[Line] = []

    def debit(account: str, amount, description: str) -> None:
        if money(amount) > 0:
            lines.append(Line(account, money(amount), Decimal("0.00"), description))

    def credit(account: str, amount, description: str) -> None:
        if money(amount) > 0:
            lines.append(Line(account, Decimal("0.00"), money(amount), description))

    debit(accounts["cash"], report["cash_drop"], "Cash drop")
    debit(accounts["cards"], money(report["credit"]) + money(report["debit"]),
          f"Credit {money(report['credit'])} + debit {money(report['debit'])}")
    debit(accounts["ebt"], report["ebt"], "Food stamp / EBT")
    for p in report["paid_outs"]:
        if p["kind"] == "cash":
            debit(p.get("gl_account") or accounts["default_expense"], p["amount"], f"Paid out: {p['payee']}")

    over_short = money(report["over_short"])
    if over_short < 0:
        debit(accounts["over_short"], -over_short, "Short")

    credit(accounts["fuel_sales"], report["fuel_sale"], f"Fuel {report['gallons']} gal")
    credit(accounts["merch_sales"], report["merch_sale"], "In-store sales")
    credit(accounts["taxable_sales"], report.get("taxable_sale"), "Taxable sales")
    credit(accounts["nontaxable_sales"], report.get("nontaxable_sale"), "Non-taxable sales")
    credit(accounts["sales_tax"], report["sales_tax"], "Sales tax collected")
    if over_short > 0:
        credit(accounts["over_short"], over_short, "Over")
    return lines


def journal_number(report: dict) -> str:
    code = re.sub(r"[^A-Za-z0-9]", "", report["store_name"]).upper()[:6] or "STORE"
    return f"{code}-{report['business_date']:%Y%m%d}"


CSV_HEADER = ["Journal No.", "Journal Date", "Account Name", "Debits", "Credits", "Description", "Location"]


def to_csv(reports: list[dict], accounts: dict) -> str:
    """QuickBooks Online 'Import journal entries' format. Rows sharing a Journal No. become one entry."""
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(CSV_HEADER)
    for report in reports:
        number = journal_number(report)
        when = f"{report['business_date']:%m/%d/%Y}"
        location = report.get("qb_location") or report["store_name"]
        for line in build_lines(report, accounts):
            writer.writerow([
                number, when, line.account,
                f"{line.debit:.2f}" if line.debit else "",
                f"{line.credit:.2f}" if line.credit else "",
                line.description, location,
            ])
    return out.getvalue()
