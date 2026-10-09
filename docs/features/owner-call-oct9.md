# Feature spec: owner's requests from the Oct 8 call

_Status: **built Oct 9** · Bhajan's call notes with the owner (Oct 8), agreed Oct 9_

Four changes, built one at a time in this order, plus a **Future** section for things to do later.

| # | Change | Who sees it |
| --- | --- | --- |
| 1 | **My days** shows fuel and merchandise sales per day, month totals, "show older days", and the time each day was submitted | Employees, managers (submit time also on the owner's Review list) |
| 2 | **Co-owner** role: same powers as the owner | Owner gives it on People |
| 3 | **Inventory** page (fuel tanks + merchandise): bought vs sold, % full, when to order. Home page for owner and co-owner | Owner, co-owner |
| 4 | **Vendor dropdown** on paid outs: searchable list the owner keeps, or **Miscellaneous** with a note | Everyone filling a worksheet; owner sorts out the notes |

Principles (as always): add-only database changes, math in pure functions with unit tests, money as `Decimal`, the API decides (the screens only display), every typed change in the history log.

---

## 1. My days: sales per day, month totals, older days, submit time

**Problem.** Staff only see over/short per day. The owner wants them to see how much was sold too.

**Flow.**
- Each day row shows: date, store, **fuel sales**, **merchandise sales**, over/short, status. Under the date, small light text: **"Submitted Oct 8, 9:41 PM"** (in the phone's time zone), or "Not submitted yet".
- Rows are grouped by month. Each month has a **total line per store**: fuel, merchandise, gallons, over/short, days counted, days short. Totals count submitted, approved and exported days (not drafts, not days sent back).
- Shows the last 30 days first. **Show 30 more days** loads older ones until there are none left.
- Days sent back stay at the top with the owner's note, as now.
- Owner's **Review** list also shows the submit time under each date.

**API.** `GET /api/reports/history?until=YYYY-MM-DD&days=30&store_id=`
→ `{days: [...], months: [...], next_until: "YYYY-MM-DD" | null}`
- `days`: worksheets dated `until-days+1 … until` the person can see (their stores; owners all), each with `fuel_sale`, `merch_sale`, `gallons`, `over_short`, `status`, `submitted_at`.
- `months`: for every month touched by `days`, totals for the **whole month** per store (same statuses as above), calculated in SQL.
- `next_until`: the day before this page, or `null` when no older worksheet exists.
- `days` limited to 1-92 per page.

**Acceptance.**
- [x] Staff see fuel + merchandise per day and month totals that match the sum of the month's counted days.
- [x] "Show 30 more days" goes back until nothing is left; an employee never sees another store's days.
- [x] Submit time on My days and Review.

## 2. Co-owner

**Problem.** The owner has a partner who should see and do everything the owner can.

**Rule.** New role **`coowner`** ("Co-owner"). Same powers as the owner everywhere (reviews, reports, books, inventory, settings, people), with one safety rule:
- **Only the owner** (or the app admin) can add, change or remove an **owner or co-owner**. A co-owner can manage employees and managers. So a co-owner can never lock the owner out.
- Like owners, a co-owner sees all stores (no store list needed) and can't remove their own access.

**Data.** Migration 008 widens the role check to include `coowner` (add-only: no row changes).
**Code.** `CurrentUser.is_owner` (API) and `hasOwnerAccess()` (web) include `coowner`; `CurrentUser.is_full_owner` (owner or admin) guards the People rule above.

**Acceptance.**
- [x] Co-owner can do everything the owner can (tested on Review, Reports, Books, Inventory, Settings).
- [x] Co-owner can add an employee but not an owner or co-owner, and can't edit or delete the owner.
- [x] Co-owner shows as "Co-owner" on People and in the admin's View as list.

## 3. Inventory (fuel + merchandise), the owner's home page

**Problem.** The owner and co-owner want to see, per station, how much fuel was bought and used by type, how full the tanks are, and when to order. Same idea for merchandise. Bought amounts are typed in by the owner for now; later they come from invoice files (see Future).

### Setup (Settings → each store)
- Each tank gets a **fuel type** (Regular, Plus, Premium, Diesel, Other) and a **capacity** in gallons (optional; needed for % full).
- **Order when below**: a tank under this % full is flagged "Order soon" (default 25%, one setting for all).

### Fuel deliveries (typed by the owner)
A delivery is a **fuel purchase in the books with a date, tank and gallons**, so it shows on the P&L automatically and is never typed twice.
Fields: store, delivery date, tank, gallons, cost (can be 0 if the invoice comes later), vendor (fuel vendors), note / invoice #.
Merchandise purchases can be typed the same way (store, date, vendor, amount, note) and are merchandise purchases in the books.

### Fuel: what the page shows (one card per store, for a month)
Per tank:
```
Latest reading   = gallons from the latest worksheet (submitted / approved / exported) up to the month's end
On hand          = latest reading + deliveries after it
% full           = on hand ÷ capacity
Delivered        = gallons of deliveries to the tank this month
Used             = opening reading + deliveries after it − closing reading
                   (opening = last reading before the month, else the first in the month;
                    closing = last reading in the month; needs 2 readings)
Average per day  = used ÷ days between the opening and closing readings
Days left        ≈ on hand ÷ average per day
Order soon       = % full below the setting, or about 3 days or less left
```
Per fuel type: the same totals added up (so two Regular tanks show as one Regular line).
Store check: **pump gallons** (from the worksheets) vs **used by tank readings** over the same days, with the difference in gallons and %. Shown only when every tank was read on the same opening and closing days (otherwise the windows don't match and the number would mislead).
Money: fuel sales, delivered cost, **average sell price per gallon** vs **average cost per gallon** = margin per gallon.

### Merchandise: what the page shows (per store, for a month)
```
Sold        = merchandise sales on counted days (approved; toggle adds days waiting for review)
Bought      = typed merchandise purchases + paid outs to merchandise vendors on counted days
Bought as % of sales = bought ÷ sold
```
Plus per merchandise vendor: bought this month, last purchase date and days since. (Item-level stock needs invoice lines: Future.)

### API (owner / co-owner)
| Method | Path | Does |
| --- | --- | --- |
| GET | `/api/inventory?month=&store_id=&include=` | fuel + merchandise per store |
| POST / PATCH / DELETE | `/api/books/entries` | now also takes `entry_date`, `tank`, `gallons` (deliveries). PATCH keeps them when not sent |
| PATCH | `/api/stores/{id}` | also takes `tank_specs: [{name, grade, capacity}]` |

Rules checked by the API: gallons only on fuel purchases, and then a store, a date and one of that store's tanks are required; the date must be in the entry's month.

**Data (migration 008).** Add-only: `ledger_entries.entry_date`, `.tank`, `.gallons`; `stores.tank_specs` jsonb (fuel type + capacity per tank name; `tanks` stays the list of names); setting `reorder_percent`.

**Math.** `app/modules/inventory/math.py`, pure functions, unit-tested (readings, deliveries, missing readings, rounding).

**Home page.** Owner and co-owner land on **Inventory** (first menu item). Review stays one tap away.

**Acceptance.**
- [x] Worked example by hand matches the page (used, % full, days left, pump vs tank, cost per gallon).
- [x] Deliveries appear on the P&L as fuel purchases; editing one on the P&L doesn't lose its gallons.
- [x] Employees and managers can't open Inventory or its API.

## 4. Vendor dropdown with Miscellaneous

**Problem.** Staff type vendor names freely, so the same vendor is spelled many ways ("Coca Cola", "coke", "Coca-Cola Co").

**Flow.**
- The owner keeps the vendor list (Reports → Vendors, as now).
- On a paid-out line, **Vendor** is a **searchable dropdown** of the active vendors. Last option: **Miscellaneous (not on the list)**, which asks for a **note** ("what was it and who was paid").
- Before the day can be **submitted**, every paid-out line must be a vendor from the list or Miscellaneous with a note. Drafts save anything (autosave). If the owner has no vendors yet, any name is accepted (as today).
- The owner's **Vendors** page lists **Miscellaneous paid outs to sort out** (date, store, amount, note) with **Add as vendor**. The day view shows the note too.

**API.**
- `GET /api/vendors/names` (anyone signed in): active vendor names and types, for the dropdown.
- Paid outs accept `note` (up to 300 characters). Submit refuses unknown names with a clear message listing them.
- `GET /api/vendors/miscellaneous?days=90` (owner): Miscellaneous lines to sort out.

**Data (migration 008).** `paid_outs.note` (add-only).

**Acceptance.**
- [x] Employee picks a vendor by typing part of the name; Miscellaneous needs a note; submit refuses names not on the list.
- [x] Old days with old spellings still show and still count on reports (nothing rewritten).
- [x] Owner sees Miscellaneous notes and adds a vendor in one tap.

## Independent review (Oct 9)
A separate reviewer (spec + diff only) wrote tests against the change (`services/api/tests/test_review_oct9.py`). Found and fixed:

| # | Severity | Bug | Fix |
| --- | --- | --- | --- |
| 1 | Medium | Renaming a tank in Settings lost its readings and deliveries on Inventory (matched by name) | Settings sends the old name; the tank keeps its old names (`aliases`) and Inventory matches all of them |
| 2 | Medium-low | Changing only the gallons (or tank) of a delivery was refused | Delivery rules checked after merging with the saved entry |
| 3 | Low | `/api/reports/history?until=0001-01-10` gave a 500 | Dates before 2000 refused (400) |
| 4 | Low | An owner with many stores could get a cut-short history page | No row cap on a page (at most 92 days) |

Also: deliveries can't be dated in the future; "today" is the stores' time zone (`BUSINESS_TIMEZONE`, default America/New_York), not the server's UTC; the Settings screen refuses an empty "Order soon" %.

**On hand.** A delivery typed after the latest tank reading is added to the tank's on-hand gallons right away (shown as "+ N delivered since").

**Known limits.** Owners editing a submitted day aren't held to the vendor list (the rule is on submit). Merchandise purchases typed for "All stores (shared)" count on the P&L but not on a store's Inventory card.

---

## Future (agreed, not built yet)

| Idea | How | Notes |
| --- | --- | --- |
| **Invoice files → deliveries / purchases** | Owner uploads a PDF or photo of a fuel or grocery invoice; AI reads vendor, date, gallons / items, amount into a **draft** the owner confirms | Same "AI fills drafts, people confirm" rule; builds on [ai-report-scan.md](ai-report-scan.md) |
| **Reed Oil (fuel) and ABL Wholesale (grocery)** | No public API found for either. Route: (1) invoice PDF / photo scan above; (2) if their customer website has a CSV/Excel download, an "Import invoices" for that layout; (3) EDI only if they offer it and it's free | Ask the owner how invoices arrive (paper, email PDF, website) and if item-level detail matters |
| **Erie Bank feed** | Through a bank-data service (Plaid lists Erie Bank). Read-only balances and transactions: fills the bank balance on the Balance Sheet, matches deposits to cash drops, brings payments in as draft purchases / expenses | Plaid's free trial allows 10 live connections; after that it costs money (budget is $0: check before relying on it). Bank key stored encrypted, server only. Owner signs in to the bank himself |
| **Old vendor spellings** | Owner maps an old spelling to a vendor once ("coke" → Coca-Cola) so past paid outs group correctly | Today: old names show as "not on the list" |
| **Item-level merchandise stock** | Needs invoice lines (above) and register item sales | Later |
