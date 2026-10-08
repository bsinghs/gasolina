# Feature spec: owner's Oct 8 worksheet (v3) and reports

_Status: **phases 1, 2 and 3 done (Oct 8)** · Oct 8, 2026 · From the owner's edited copy of the worksheet preview_

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

## Phase 3: Vendors, Profit & Loss, Balance Sheet (owner only)

Bhajan (Oct 8): build it; keep it simple, understandable and testable; test rigorously. Purchases and expenses are **typed in by the owner** (no bank or QuickBooks import).

### Principles
- **Add-only database change** (migration 007: three new tables). Nothing existing is altered, so no data can be lost.
- **Math in pure functions** (`app/modules/books/math.py`: P&L and balance sheet), unit-tested without a database. Routers only check the role; services only fetch rows and call the math.
- **Money is `Decimal`** end to end; the API sends amounts as exact strings.
- **Sales come from approved days** (same rule as Reports; toggle adds days waiting for review). Drafts and sent-back days never count.
- Every add / change / delete of a typed entry is written to the history log (`audit_log`, action `ledger.*` / `balance.*` / `vendor.*`).
- **Store**: every entry belongs to one store, or to **All stores (shared)**, e.g. insurance for the group. A store's P&L shows its own entries; "All stores" shows everything.

### Vendors
- List of vendors, each **Cost of goods** (Fuel or Merchandise) or **Expense**. Name unique (ignoring case). Deactivate instead of delete once used.
- Daily **paid outs** are matched to vendors **by name** (ignoring case and extra spaces). Unmatched names show as "not on the list" so the owner can add them in one tap.
- **Spending by vendor** for a month or a year: typed entries + paid outs on counted days; cost of goods / expense / not on list / total / share.

### Profit & Loss (one month; year overview of 12 months)
```
Revenue        = fuel sales + merchandise sales            (PA tax is NOT revenue; shown for information)
Cost of goods  = typed fuel purchases + typed merchandise purchases
               + paid outs to cost-of-goods vendors        (if "count paid outs" is on)
Gross profit   = revenue − cost of goods
Expenses       = typed expenses + paid outs to expense vendors + paid outs to vendors not on the list
Cash over/short= sum of daily over/short (a shortage lowers profit, an overage raises it)
Net profit     = gross profit − expenses + cash over/short
```
"Count paid outs from the daily sheets" is on by default; turn it off if the same payments are also typed in, so nothing counts twice.

### Balance Sheet (as of the end of a month)
```
Assets       = typed asset lines (cash in bank, cash on hand, fuel / merchandise inventory, equipment…)
Liabilities  = typed liability lines + PA sales tax collected that month (owed to the state)
Equity       = typed equity lines (owner investment, draws as negative, opening retained earnings)
             + profit to date (sum of monthly net profit, from the first month with data)
Check        = Assets − (Liabilities + Equity)   → 0.00 means balanced; otherwise the difference is shown
```
- Bank balances are **typed from the bank statement**. (His file added cash drops to the bank automatically, which ignores withdrawals and bank fees, so it drifts; typing the statement balance is simpler and correct.)
- **Copy last month's lines** fills an empty month from the latest earlier month; it never overwrites a month that already has lines.
- **All stores / whole business** sheet = shared lines + every store's own lines (labelled with the store), with tax and profit to date for all stores. Each store's sheet = its own lines.
- Saves and copies take a lock per month (+ store), so a double tap waits instead of doubling lines.
- Profit to date follows the same "count paid outs" choice as the P&L.
- **Tax owed** = PA tax collected in that month only (assumes he pays the state monthly). Ask the owner/accountant if older unpaid tax should carry over.

### API (all owner only)
| Method | Path | Does |
| --- | --- | --- |
| GET / POST | `/api/vendors` | list / add |
| PATCH / DELETE | `/api/vendors/{id}` | edit, deactivate / delete (only if unused) |
| GET | `/api/vendors/spending?period=month\|year&value=&store_id=` | spending by vendor |
| GET / POST | `/api/books/entries?month=&store_id=` | typed purchases and expenses for a month / add one |
| PATCH / DELETE | `/api/books/entries/{id}` | change / remove one |
| GET | `/api/books/pnl?month=&store_id=&include=&count_paid_outs=` | statement for a month |
| GET | `/api/books/pnl-year?year=&store_id=…` | 12 months: revenue, cost of goods, expenses, net |
| GET / PUT | `/api/books/balance?month=&store_id=` | balance sheet / replace that month's typed lines |
| POST | `/api/books/balance/copy-previous?month=&store_id=` | copy the latest earlier month (only into an empty month) |

### Acceptance
- [x] Unit tests for P&L and balance math (every line above, rounding to the cent, empty month).
- [x] API tests: vendors CRUD + unique names + delete rule; entries CRUD + history; P&L matches hand-worked example; paid-out toggle; store vs all; balance check; copy-previous never overwrites; employees and view-as refused / read-only.
- [x] Screens on laptop and phone; numbers cross-checked against SQL.
- [x] Independent review of the change; findings fixed.
- [x] His QuickBooks chart of accounts kept as a reference (`docs/reference/owner-chart-of-accounts.md`) for future export mapping.

### Independent review (Oct 8)
A separate reviewer (spec + diff only) found 8 bugs, each proven by a failing test (`services/api/tests/test_review_books.py`); all fixed:

| # | Severity | Bug | Fix |
| --- | --- | --- | --- |
| 1 | High | Double tap on "Copy last month" copied the lines twice | Month lock (`pg_advisory_xact_lock`); second request waits, then is refused |
| 2 | High | Two Saves of an empty month doubled the lines | Same lock; second save replaces |
| 3 | Med-high | "All stores" balance sheet left out each store's own lines but included their profit | Group sheet adds every store's lines (labelled) |
| 4 | Medium | Balance sheet ignored the "count paid outs" choice | `count_paid_outs` on `/books/balance` + checkbox |
| 5-6 | Medium / low | Year 0000 or 9999 gave 500 errors | Years limited to 2000-2099 (clean 400/422) |
| 7 | Low | Balance line named only with spaces saved with an empty name | Name validator |
| 8 | Low | New entries could use a deactivated vendor | Refused (an edited entry may keep its vendor) |

Also from the review: amounts the screen can't read ("12abc") are refused instead of saved as 0.00; "(500.00)" means −500; vendor changes keep the before-values in history. Known limits: renaming a vendor or changing its type re-sorts past paid outs (matching is by name); the balance sheet recalculates every month since the start (fine for years of data).
