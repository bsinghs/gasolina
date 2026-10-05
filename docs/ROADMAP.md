# Roadmap: replacing QuickBooks, step by step

_Updated Oct 4, 2026: the owner pays Intuit about **$30/month per store** and wants to stop, using our own database instead._

**Goal:** Shift Close becomes the station's books for day-to-day work, so QuickBooks can be cancelled. **Not** a full accounting product: only what this business uses, and anything tax-critical checked by his accountant before we switch.

## What QuickBooks does today → where it goes

| Need | In Shift Close | Status |
| --- | --- | --- |
| Daily sales, cards, cash, over/short | Daily worksheet + approval | ✅ Live |
| Paid-outs per day | Worksheet paid-outs (cash / check) | ✅ Live |
| Monthly totals per store / all stores | Monthly reports | Spec: [features/monthly-reports.md](features/monthly-reports.md) |
| Expenses / vendor bills | Bills: photo → AI reads → owner approves | To spec |
| **Profit & loss** per store and combined | Simple double-entry ledger behind the scenes (every approved day / bill posts balanced entries; we already build these for the QuickBooks CSV) | To spec |
| Sales tax report | From tax collected per day | To spec |
| Bank deposits | Deposit tracking per store | To spec |
| **Year-end package for the accountant** | P&L, expense detail, sales-tax summary, general ledger as Excel/PDF | To spec. **Accountant must approve** |
| Payroll, 1099s | **Not built here.** Keep a cheap payroll service if he uses payroll | Ask |
| Bank statement matching | Later, maybe | Ask |

## How we switch safely

1. **Ask** the owner and his accountant what QuickBooks is used for (questions below).
2. **Build** the missing pieces, one feature at a time (spec → build → independent review → tests).
3. **Run both side by side for 1-2 months.** The accountant compares our P&L and sales tax with QuickBooks.
4. **Export QuickBooks history** (reports + full transaction list), keep it, then cancel.

## Questions for the owner / accountant

- Payroll in QuickBooks? Paying vendors / writing checks from it? Matching the bank statement in it?
- What does the accountant need at year-end: a QuickBooks login or reports?
- One QuickBooks company per store? (If QuickBooks stays a while: one company with locations may cost less.)
- Would the accountant accept Excel/PDF reports, or insist on an accounting app? (Middle path: a free accounting app such as Wave just for the year-end package; check current terms.)

## Principles

- Money numbers are calculated in the API, stored exactly, and every entry balances (debits = credits).
- Nothing is posted to the books without a person approving it.
- Records are never deleted, only corrected with a new entry (keeps the history the accountant needs).
- Keep it simple: only what this business uses **weekly**.
