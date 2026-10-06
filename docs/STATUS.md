# Status and next steps

_Last updated: Oct 5, 2026_

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

## After the demo (in order)

1. **Shift-report photo upload** on the worksheet (tables already exist)
2. **AI report scanning**: photo of the register report prefills the worksheet, with cross-checks. Spec: [features/ai-report-scan.md](features/ai-report-scan.md) (covers 1 and 2)
3. **Direct QuickBooks posting**: `services/quickbooks` via Intuit's API instead of CSV
4. **Monthly reports** (one or several stores): spec [features/monthly-reports.md](features/monthly-reports.md)
5. Reminders when a store hasn't submitted

## Wishlist: quality and training (agreed Oct 4, do later)

1. **Automatic checks on every push** (GitHub Actions): API tests + web build, red/green on each change. $0
2. **Click tests with Playwright**: employee submits on a phone, owner sends back, fix, approve, export. Runs on every push. $0
3. **Error alerts** (e.g. Sentry free plan): email when the app errors on someone's phone. $0 tier
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
