# Status and next steps

_Last updated: Oct 10, 2026_

## Done

| Area | What exists | Checked by |
| --- | --- | --- |
| Database | 9 tables, plain SQL migration, demo seed script | Migration runs clean on Postgres 16 |
| API | Sign-in check, roles, stores, people, worksheets, approval workflow, QuickBooks CSV, check paid-outs CSV, raw CSV, settings | 5 automated tests, including a full submit → send back → fix → approve → export run |
| Web app | Sign in, worksheet (autosave, live totals), my days, review queue (with missing days), day detail with journal-entry preview, export, people, settings | Clicked through end to end in a browser, phone and laptop sizes |
| QuickBooks | Each approved day → one balanced journal entry, CSV in QuickBooks Online import format | Spec's worked example balances at $5,644.50 |
| Docs | README, architecture with diagrams, deploy checklist | |
| Worksheet v2: taxable / non-taxable (Oct 5) | Calculated from the PA sales tax: taxable = tax ÷ rate (Settings, 6%), non-taxable = merchandise − taxable. Total sales = Fuel + Merch + Tax. Migrations 004, 005. Spec: [features/worksheet-v2-fields.md](features/worksheet-v2-fields.md) | 25 API tests (incl. TRUTH 9 Oct 1: $71.29 tax → $1,188.17 / $2,208.43); laptop + phone screenshots |
| Review queue v2 + admin View as (Oct 5) | Count boxes are filters; missing days grouped per store (date chips open the worksheet), follow From/To, past days only, from the store's start. App admin can **View as** any owner/manager/employee from the header: read-only, blue banner, hidden from everyone else | 26 API tests (view-as read-only + admin-only); browser click-through |
| Worksheet v3, phase 1 (Oct 8) | Owner's edited form: TRUTH logo + metallic header, gold store name, Fuel / Merch / Tax in one row, **ending inventory per tank** (tank names per store in Settings), paid-out **vendor name** suggestions. Migration 006. Spec: [features/worksheet-v3-and-reports.md](features/worksheet-v3-and-reports.md) (phases 2-3: monthly/yearly, P&L, balance sheet, vendors) | 27 API tests; laptop + phone click-through |
| Reports: month / quarter / year (Oct 8) | Owner-only Reports tab. Read-only totals from approved days (toggle adds days waiting for review): sales, fuel + gallons, merchandise + taxable / non-taxable, PA tax, over/short; by store; day-by-day or month-by-month; Excel download. Spec: [features/monthly-reports.md](features/monthly-reports.md) | 28 API tests (sums to the cent, quarter months, toggle, owner-only, worksheets unchanged); totals cross-checked in SQL; laptop + phone |
| Books: Vendors, Profit & Loss, Balance Sheet (Oct 8) | Owner-only, under Reports. Vendor list (cost of goods fuel / merchandise, or expense) with spending by vendor; P&L per month (sales from approved days, typed purchases / expenses, daily paid outs sorted by vendor, over/short) + year view; Balance Sheet at month end (typed lines, PA tax owed, profit to date, check). Add-only migration 007, math in pure functions, every change in history. Spec: [features/worksheet-v3-and-reports.md](features/worksheet-v3-and-reports.md) | 61 API tests (7 math unit, 12 API, 14 from independent review); 22 browser checks owner / employee / view-as / phone; P&L cross-checked in SQL |

| Owner's call, Oct 8 (Oct 9) | **My days** for staff: fuel + merchandise per day, month totals, "Show 30 more days", submit time (also on Review). **Co-owner** role: sees every owner page, **view only** (no change buttons; API refuses changes). Permissions are one table (API `core/permissions.py` = web `lib/access.ts`). **Inventory** = owner / co-owner home: per tank on hand, % full, delivered, used, days left, "Order soon", pump vs tank check, price vs cost per gallon; merchandise bought vs sold; fuel deliveries typed in become fuel purchases on the P&L. **Vendor dropdown** on paid outs (searchable; Miscellaneous + note; checked on submit) and a "to sort out" list for the owner. Add-only migration 008. Spec: [features/owner-call-oct9.md](features/owner-call-oct9.md) (Future: Erie Bank feed, Reed Oil / ABL invoices) | 93 API tests (9 inventory math unit, 4 permissions unit, 11 API, 8 from independent review: 4 bugs found and fixed); browser click-through owner / co-owner / employee, laptop + phone |

| Versions & releases (Oct 9) | `VERSION` (2026.10.3) + `CHANGELOG.md` + git tags per release; version and commit on `/api/health` and at the bottom of every page (amber if screens and API differ); release log (`releases` table, migration 009) in Settings; `make release`. Spec: [features/releases-and-versions.md](features/releases-and-versions.md) | 95 API tests (release log: one row per new version/commit, restarts don't add rows) |

## Next: get it live (you)

Follow [DEPLOY.md](DEPLOY.md). About 30–45 minutes.

- [x] Supabase project created, tables in place (Oct 3)
- [x] Supabase: database password reset, Session pooler connection string saved
- [x] Google sign-in: Google Cloud project `gasolina-510519`, OAuth client, enabled in Supabase (Testing mode: test users only)
- [x] API live on Render: https://gasolina-api-c7yd.onrender.com (`/api/health` OK, connected to Supabase)
- [x] API moved to Google Cloud Run (Oct 4): https://gasolina-api-v7l555dt2a-uk.a.run.app (`/api/health` OK). `make live` uses it. Render service **suspended** Oct 5
- [x] Cloudflare Pages (Oct 4): https://shift-close.pages.dev (root `apps/web`, build `npm run build`, output `dist`, settings in `apps/web/.env.production`). Rebuilds on every push to main
- [x] Connected the ends (Oct 4): API `CORS_ORIGINS` includes the site; Supabase Site URL + Redirect URLs set. Owner signed in on a phone at https://shift-close.pages.dev
- [ ] Sign in as owner, add stores and people, run one day through on a phone

## Test environment (Oct 5)

- [x] Second Supabase project `gasolina-test`, `test` branch → https://test.shift-close.pages.dev, `deploy.sh test`, TEST banner, admin **Reset test data** (test only)
- [ ] Owner of the Google client: add test callback; enable Google in test Supabase; set test DB password; first `deploy.sh test`
- Workflow: `test` branch first, then merge to `main` (see CLAUDE.md)

## Next: before the demo

- [ ] Open the app a minute early (Render's free plan sleeps after 15 minutes idle)
- [ ] Set the QuickBooks account names in Settings to his real chart of accounts
- [ ] Demo script: employee submits on phone → owner sends back once → approves → export → import into a QuickBooks sandbox

Long-term direction: [ROADMAP.md](ROADMAP.md): replace QuickBooks (~$30/month per store) step by step, with the accountant's OK.

## Latest (Oct 10): admin Monitor (2026.10.5)
App admin only: **Monitor** page with who's online now (incl. screen and phone/computer), requests per minute for the last hour, usage since the last release / today / 7 / 30 days (visits, active minutes, screens, errors, slowest requests) and the full history of what people did, now including people, store and settings changes. One request-log row per API request (migration 010, kept 90 days; no ids, values or IP). Spec: [features/admin-monitor.md](features/admin-monitor.md). 106 API tests.

## After the demo (in order)

1. **Shift-report photo upload** on the worksheet (tables already exist)
2. **AI report scanning**: photo of the register report prefills the worksheet, with cross-checks. Spec: [features/ai-report-scan.md](features/ai-report-scan.md) (covers 1 and 2)
3. **Direct QuickBooks posting**: `services/quickbooks` via Intuit's API instead of CSV
4. **Monthly reports** (one or several stores): spec [features/monthly-reports.md](features/monthly-reports.md)
5. Reminders when a store hasn't submitted

## Wishlist: quality and training (agreed Oct 4, do later)

1. ~~Automatic checks on every push~~: done Oct 9 (GitHub Actions: tests + web build, test API auto-deploy, release tags, Deploy production button). Spec: [features/ci-cd.md](features/ci-cd.md). Live: keyless sign-in set up, first automatic test deploy and first production deploy by button (2026.10.4, Oct 9)
2. **Click tests with Playwright**: employee submits on a phone, owner sends back, fix, approve, export. Runs on every push. $0
3. **Error alerts** (e.g. Sentry free plan): email when the app errors on someone's phone. $0 tier. Partly covered Oct 10: server errors and refused requests now show on the admin **Monitor** (no email yet)
4. ~~Test copy of the app~~: done Oct 5 (finish setup steps above)
5. **Training from the same Playwright scripts**: 60-second phone video + one-page picture guide for employees; owner walkthrough. Re-run to refresh when screens change
6. Builder + independent reviewer for each new feature (start with taxable / non-taxable)

## Open questions for the owner

- QuickBooks Online or Desktop? Exact account names?
- Which 3 QuickBooks tasks take the most time each week? (Decides what we bring in first)
- One shift per day, or one worksheet per shift?
- Over/short amount that should trigger a warning
- Close out once a day, or every shift? (Day / Night / Mid in his worksheet)
- Monthly reports: calendar month or the register's close-month date? Which numbers matter most?
- Photos of the daily shift-close report and any fuel/pump report (for AI scanning)
