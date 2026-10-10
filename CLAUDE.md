# CLAUDE.md: how to work in this repo

Read this first in every session. Shift Close: gas-station employees fill the **daily sales worksheet** on their phone, the owner **approves or sends it back**, approved days **export to QuickBooks**.

## Layout

```
apps/web/              React + Vite + TypeScript screens. Talks ONLY to the API, through src/api/client.ts
services/api/          Python 3.12 FastAPI. All business rules, auth checks, database access
  app/core/            config (env vars), db (psycopg pool), auth (Supabase JWT / dev header), errors
  app/modules/<name>/  one folder per feature: router.py (HTTP), schemas.py (Pydantic), service.py (logic + SQL)
  scripts/             migrate.py (applies database/migrations), seed_demo.py
  tests/               pytest
database/migrations/   numbered plain SQL (001_, 002_ ...). Applied in order on every API start
deploy/cloudrun/       Google Cloud Run deploy (run deploy.sh in Cloud Shell)
docs/                  STATUS.md (done/next), ARCHITECTURE.md, DEPLOY.md, features/ (one spec per feature)
render.yaml            old Render host (being retired)
Makefile               make demo · make live · make test · make stop · make reset-demo
```

## Commands

| Do | Command |
| --- | --- |
| Run everything locally with sample data (Docker) | `make demo` → http://localhost:5173, sign in by picking Owner/Employee |
| Screens locally against the real online API | `make live` |
| API tests | `make test` (needs Python 3.10+). Workflow tests also need `TEST_DATABASE_URL` |
| Type-check + build the web app | `cd apps/web && npm run build` |
| Deploy the API | Cloud Shell: `cd ~/gasolina && git pull && bash deploy/cloudrun/deploy.sh test` (then `production`) |

## Two copies of the app: test first, then production

| | **Test** (fake data) | **Production** (real data) |
| --- | --- | --- |
| Website | https://test.shift-close.pages.dev (git branch `test`) | https://shift-close.pages.dev (branch `main`) |
| API | Cloud Run `gasolina-api-test` · `deploy.sh test` | Cloud Run `gasolina-api` · `deploy.sh production` |
| Database | Supabase `gasolina-test` (`tceosbqbkmkicgmkpqdz`) | Supabase `gasolina` (`uhwhfrwpuysestjdqawz`) |
| Look | Orange TEST banner, `[TEST]` tab title | Normal |
| Extras | Admin **Reset test data** (Settings) | None: real data can't be wiped from the app |

Flow: commit to `test` → push → try it on the test site (and `deploy.sh test` if the API changed) → merge `test` into `main` → push → `deploy.sh production`.
`APP_ENV` (API) and `VITE_APP_ENV` (web) say which copy is running; web settings per copy are in `apps/web/.env.production`, `.env.test`, `.env.demo`.

## Rules (don't break these)

1. **Screens never touch the database.** Browser → API → Postgres. The web app has no database credentials.
2. **Money is `Decimal`**, rounded with `reconciliation.money()`. Never `float`. Columns are `numeric(12,2)`.
3. **The API decides everything**: totals, over/short, who can see/do what. The web app only displays. Worksheet math lives in `services/api/app/modules/reports/reconciliation.py`, the owner's books (P&L, balance sheet) in `services/api/app/modules/books/math.py` (pure functions, tested).
4. **Every permission check happens in the API**, using `current_user` / `owner_only` from `app/core/auth.py`. Employees only see their own stores. Roles: `employee`, `manager`, `owner`, `coowner` (sees every owner page, **view only**: no change buttons, and the API refuses any non-GET), `admin`. Who may do what is **one permissions table**: `app/core/permissions.py` (API) = `apps/web/src/lib/access.ts` (screens): `see_all_stores`, `make_changes`, `manage_owners`. Use `user.is_owner` / `user.can_change` / `user.is_full_owner` and `useViewOnly()`, not role-name comparisons, admin = app support (from `ADMIN_EMAILS`; owner powers, hidden from the owner's People list, not editable by the owner; actions still show by name in history). Use `user.is_owner` / `hasOwnerAccess()` for "has owner powers". Admin-only **View as** (`X-View-As: <person id>` header) shows the app as another person, **read-only** (any non-GET is refused), so nothing is ever done under someone else's name.
5. **Database changes = a new migration file** (`database/migrations/00N_name.sql`). Never edit an applied migration. Tables stay locked (RLS on, no policies); see 002.
6. **No secrets in git.** Secrets live in Google Secret Manager / host env vars. `Temp_DOCS/` is personal and gitignored: never commit it, never copy its contents into tracked files.
7. **AI fills drafts; people confirm.** Anything an AI reads goes into a draft and is marked in `field_sources` (`typed` / `ai` / `ai_corrected`). Code, not AI, checks the numbers add up.
8. **Keep it simple.** One module per feature, plain SQL, no ORM, no new framework without a reason written in the feature spec.
9. Python uses `X | None` types: Python 3.10+ only. `make demo` runs the API in Docker for that reason.

## How we build a feature

1. **Spec first**: `docs/features/<feature>.md` (problem, flow, API, data, checks, acceptance criteria, stories). Agree it before coding.
2. **Plan**, then build one story at a time, smallest working slice first.
3. **Tests** for any math, permission or workflow change (`services/api/tests/`).
4. **Check it**: `make test`, `npm run build`, click through with `make demo` (owner + employee).
5. **Update `docs/STATUS.md`** (and ARCHITECTURE.md if the shape changed). Commit with a clear message.

## Environment

- API settings (env vars, see `services/api/app/core/config.py`): `DATABASE_URL`, `AUTH_MODE` (`supabase` | `dev`), `SUPABASE_URL`, `BOOTSTRAP_OWNER_EMAIL` (demo/first owner), `ADMIN_EMAILS` (app admins), `CORS_ORIGINS`.
- Web settings: `apps/web/.env.demo`, `.env.live` (`VITE_API_URL`, `VITE_AUTH_MODE`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`; all public).
- Hosts: API on Google Cloud Run (`gasolina-510519`, `us-east4`); database + sign-in on Supabase (`uhwhfrwpuysestjdqawz`, us-east-1); screens to Cloudflare Pages (next). Trial budget is **$0/month**: flag anything that costs money.
- `AUTH_MODE=dev` trusts an `X-Dev-Email` header. **Only** for local demo; never on a public host.

## Current focus

See `docs/STATUS.md`. Latest: owner's Oct 8 call (My days sales, co-owner, Inventory home, vendor dropdown) → `docs/features/owner-call-oct9.md` (also lists future bank feed / vendor invoices). Next feature: **AI report scan** → `docs/features/ai-report-scan.md`.
