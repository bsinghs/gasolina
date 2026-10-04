# Status and next steps

_Last updated: Oct 4, 2026_

## Done

| Area | What exists | Checked by |
| --- | --- | --- |
| Database | 9 tables, plain SQL migration, demo seed script | Migration runs clean on Postgres 16 |
| API | Sign-in check, roles, stores, people, worksheets, approval workflow, QuickBooks CSV, check paid-outs CSV, raw CSV, settings | 5 automated tests, including a full submit → send back → fix → approve → export run |
| Web app | Sign in, worksheet (autosave, live totals), my days, review queue (with missing days), day detail with journal-entry preview, export, people, settings | Clicked through end to end in a browser, phone and laptop sizes |
| QuickBooks | Each approved day → one balanced journal entry, CSV in QuickBooks Online import format | Spec's worked example balances at $5,644.50 |
| Docs | README, architecture with diagrams, deploy checklist | |

## Next: get it live (you)

Follow [DEPLOY.md](DEPLOY.md). About 30–45 minutes.

- [x] Supabase project created, tables in place (Oct 3)
- [x] Supabase: database password reset, Session pooler connection string saved
- [x] Google sign-in: Google Cloud project `gasolina-510519`, OAuth client, enabled in Supabase (Testing mode: test users only)
- [x] API live on Render: https://gasolina-api-c7yd.onrender.com (`/api/health` OK, connected to Supabase)
- [ ] Move the API to Google Cloud Run (free, no 50 s wake-up): run `deploy/cloudrun/deploy.sh` in Cloud Shell, point `apps/web/.env.live` at it, then retire Render
- [ ] Cloudflare Pages: root `apps/web`, build `npm run build`, output `dist`; fill the `VITE_*` variables
- [ ] Connect the ends: `CORS_ORIGINS` on the API, Site URL + Redirect URLs in Supabase
- [ ] Sign in as owner, add stores and people, run one day through on a phone

## Next: before the demo

- [ ] Open the app a minute early (Render's free plan sleeps after 15 minutes idle)
- [ ] Set the QuickBooks account names in Settings to his real chart of accounts
- [ ] Demo script: employee submits on phone → owner sends back once → approves → export → import into a QuickBooks sandbox

## After the demo (in order)

1. **Shift-report photo upload** on the worksheet (tables already exist)
2. **AI report scanning**: photo of the register report prefills the worksheet, with cross-checks. Spec: [features/ai-report-scan.md](features/ai-report-scan.md) (covers 1 and 2)
3. **Direct QuickBooks posting**: `services/quickbooks` via Intuit's API instead of CSV
4. Reminders when a store hasn't submitted; weekly and monthly reports

## Open questions for the owner

- QuickBooks Online or Desktop? Exact account names?
- One shift per day, or one worksheet per shift?
- Over/short amount that should trigger a warning
- Photos of the daily shift-close report and any fuel/pump report (for AI scanning)
