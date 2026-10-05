# Roadmap: Shift Close and QuickBooks

_Agreed direction, Oct 4, 2026_

**Goal:** over time, bring most of the owner's day-to-day QuickBooks work into this app, **without rebuilding QuickBooks**.

**Principle:** Shift Close is the gas station's **front office**; QuickBooks stays **the books** (the single source of truth for accounting). We add what a station does daily that QuickBooks is clumsy at, and push the results into QuickBooks automatically. We never keep a second set of accounts that can disagree.

| Phase | Add to Shift Close | QuickBooks link |
| --- | --- | --- |
| **Now** | Daily worksheet + approval · monthly reports · AI photo scan of the register report | Journal-entry CSV import |
| **Next** | **Direct posting** (no CSV); pick accounts/vendors/locations pulled from QuickBooks | Intuit QuickBooks Online API (OAuth, two-way) |
| **Then** | Fuel deliveries + tank levels · vendor bills (photo → AI reads → owner approves) · lottery / scratch-off counts · bank deposit tracking | Bills, deposits, journal entries posted to QuickBooks |
| **Later** | Owner dashboard across stores · alerts (short days, missing closes, low tanks) · employee hours | Payroll stays in QuickBooks / payroll provider |
| **Leave to QuickBooks** | Taxes, payroll, bank reconciliation, financial statements, accountant's work | |

**How we keep it simple**

1. One feature at a time: short spec in `docs/features/`, build, independent review, tests.
2. Only what the owner uses **daily**. Ask him: "Which 3 QuickBooks tasks take you the most time?" Those come first.
3. Every money number is calculated in the API and posted to QuickBooks; people approve before anything is posted.

**Open question for the owner:** QuickBooks **Online** or **Desktop**? (Direct posting needs Online; Desktop would stay on file import.)
