# Feature spec: owner's Oct 8 worksheet (v3) and reports

_Status: **phases 1 and 2 done (Oct 8)**, phase 3 later · Oct 8, 2026 · From the owner's edited copy of the worksheet preview_

The owner (with an AI's help) turned the shared worksheet preview into a small bookkeeping app: **Daily**, **Reports** (Monthly, Yearly, Profit & Loss, Balance Sheet, Inventory) and **Vendors**. His file is a stand-alone page that keeps data in the browser; we build the same ideas into Shift Close, on our database, with the API doing the math.

## Decisions (Bhajan, Oct 8)

| # | Question | Answer |
| --- | --- | --- |
| 1 | Order | Daily form first, then Monthly/Yearly, then P&L, Balance Sheet, Vendors |
| 2 | Tanks | Default per store: Tank 1 – Regular, Tank 2 – Regular, Tank 3 – Premium. Owner can rename/add per store in Settings |
| 3 | Who sees what | Employees: Daily only. Reports and Vendors: owner only |
| 4 | Purchases / expenses on the P&L | Typed in by the owner (manual), as in his file |

## Phase 1: daily form (this change)

| Change | Details |
| --- | --- |
| Logo + header | Owner's TRUTH logo (from his file) in the worksheet header; metallic navy header; store name in gold |
| Sales row | Fuel, Merchandise, PA Sales Tax on one row of three (also on phones) |
| Ending inventory | New section **Inventory Report (Ending)**: gallons left in each of the store's tanks, plus total. Saved with the day; shown on the owner's day view and in the raw CSV |
| Paid outs | "Paid to" becomes **Vendor name**, with suggestions from vendors already used at that store |
| Not taken | His "Save day to monthly sales" button: the app already saves as you type and the owner approves |

### Data
- `stores.tanks` jsonb list of tank names, default `["Tank 1 – Regular", "Tank 2 – Regular", "Tank 3 – Premium"]` (migration 006).
- `daily_reports.tank_inventory` jsonb list of `{tank, gallons}`. The tank **name is copied into the day**, so renaming a tank later doesn't change history.

### API
- `GET /api/me` and `/api/stores` include each store's `tanks`. `PATCH /api/stores/{id}` accepts `tanks` (owner; 1-10 names, kept as is when not sent).
- `PUT /api/reports` accepts `tank_inventory` (gallons ≥ 0, one decimal).
- `GET /api/reports/payees?store_id=` lists vendor names used at the store (most used first). Staff only for their own stores.

### Acceptance
- [x] Worksheet shows the logo, gold store name, three-across sales row, and one gallons box per tank with a total.
- [x] Tank readings save, reload, appear on the day view and in the raw CSV.
- [x] Owner can change a store's tank names in Settings; past days keep their old names.
- [x] Vendor names suggested on paid-out lines.
- [x] Tests for tanks and payees (incl. permissions).

## Phase 2: Monthly, Quarterly, Yearly (done Oct 8)
See [monthly-reports.md](monthly-reports.md). His version adds per-month totals of taxable / non-taxable, gallons and net over/short, and a yearly table by month (tap a month for its days). Owner only.

## Phase 3: Profit & Loss, Balance Sheet, Vendors (later, bigger)
- **Vendors**: list, each marked Cost of goods (Fuel / Merchandise) or Expense; paid outs follow it. Spending by vendor per month/year.
- **P&L** per month: revenue = fuel + merchandise (tax excluded); owner types purchases (fuel/merch, vendor) and expenses; daily paid outs can count; gross profit, net profit, 12-month view.
- **Balance Sheet** month end: owner types assets / liabilities / equity; bank balances from cash drops; PA tax collected as a liability; profit to date from P&L; check A = L + E.
- His QuickBooks **chart of accounts** (about 60 accounts, e.g. "ERIE Bank 2681", "Sales Tax Payable") is in his file: use it for account names in the export and these reports.
- Replacing QuickBooks affects his accountant and taxes: confirm with the accountant before relying on these.
