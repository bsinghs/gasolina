# Feature spec: monthly reports

_Status: **draft** · Oct 4, 2026 · Asked for by the owner (via Bhajan)_

## Problem

The owner reviews one day at a time. He also wants to see a **whole month**, for **one store or several together**: how much each store sold, how cash and cards split, and where the money went short.

## What the owner sees (new **Reports** tab, owner/admin only)

**Pick:** month (default: this month) · stores (one, several, or all) · include: approved only (default) / approved + submitted.

**1. Month summary** (one row per store, plus a **Total** row when more than one store is picked)

| Store | Days closed | Fuel | Merch | Tax | Total sales | Gallons | Credit | Debit | EBT | Cash paid out | Expected cash | Cash drop | Over / short | Days short |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|

- **Days closed** shows gaps, e.g. "28 of 31" with the missing dates listed.
- **Over / short** total in red/green, plus the count of days over the alert limit (Settings).

**2. Day by day** (for the picked stores): one row per date (× store), same columns. Click a row to open that day. Missing days are highlighted.

**3. Paid outs for the month:** grouped by payee and expense account (cash and check). Totals per account, which helps check QuickBooks.

**4. Simple charts:** daily total sales (one line per store), and daily over/short bars.

**Export:** download any of the above as CSV (Excel opens it), and **Print / PDF** (same print style as the worksheet).

## Rules

- Numbers come from the API (SQL `sum` over `daily_reports`, money as `numeric`), never added up in the browser.
- Only **approved/exported** days count by default, so unreviewed numbers don't mix in. The toggle shows submitted ones too, marked.
- Deactivated stores still appear for months they were open.
- Employees and managers don't see this (owner/admin only for now; maybe managers for their stores later).

## API

| Method | Path | Returns |
| --- | --- | --- |
| `GET` | `/api/reports/monthly?month=2026-09&store_ids=a,b&include=approved` | per-store summary + total, day rows, missing dates |
| `GET` | `/api/reports/monthly/paid-outs?month=…&store_ids=…` | paid outs grouped by payee / account |
| `GET` | `/api/exports/monthly.csv?month=…&store_ids=…` | the summary + day rows as CSV |

No database changes needed: everything is already in `daily_reports` and `paid_outs`.

## Questions for the owner

1. Calendar month, or his own period (e.g. matches the register's "Close Month" report date)?
2. Which numbers matter most at a glance? (Guess: total sales, gallons, over/short.)
3. Should managers see this for their own stores?
4. Compare with last month / same month last year? (Later.)
5. Once AI scanning exists: check the month's totals against the register's **Close Month Report** photo automatically?

## Acceptance

- [ ] Pick a month and 1, several or all stores → summary, total row, day rows, missing days.
- [ ] Sums match the individual days to the cent (test).
- [ ] Only approved days by default; toggle adds submitted, marked.
- [ ] CSV and Print / PDF work; looks right on laptop and phone.
- [ ] Employees can't open it (test).

## Stories

| # | Story |
| --- | --- |
| S1 | API: monthly summary + day rows + missing dates, with tests |
| S2 | Reports tab: pickers, summary table with total, day table |
| S3 | Paid-outs grouping + CSV export + print |
| S4 | Charts |
