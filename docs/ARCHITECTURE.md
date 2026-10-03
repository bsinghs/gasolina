# Architecture

```
 Phone / laptop browser
        │
        ▼
 apps/web  (React, static files)          Supabase Auth (Google sign-in, email link)
        │   every call: /api/...  + sign-in token   ▲
        ▼                                            │ public keys to verify tokens
 services/api  (FastAPI) ─────────────────────────────┘
        │
        ▼
 Postgres (Supabase in production, Docker locally)
```

**Rules that keep it simple**

1. **The browser only talks to the API.** It never reads or writes the database directly. Supabase is used for sign-in only; the API checks the sign-in token on every request.
2. **All business rules live in the API**: who can see which store, the status workflow, and the worksheet math. The web app shows a live preview of the totals, but the API recalculates on every save and its numbers are the ones stored.
3. **One folder per feature** in the API. Each feature module looks the same:

```
services/api/app/
├── main.py            starts the app, plugs in each module's router
├── core/              shared plumbing used by every module
│   ├── config.py      settings from environment variables
│   ├── db.py          database connection + fetch_one / fetch_all / execute
│   ├── auth.py        sign-in token -> CurrentUser (and the owner_only check)
│   └── errors.py      not_found(), forbidden(), ...
└── modules/
    ├── me/            who am I, which stores can I use
    ├── stores/        gas station locations
    ├── people/        invite list and roles
    ├── reports/       the daily worksheet and its approval workflow
    │   ├── router.py          HTTP endpoints (thin)
    │   ├── schemas.py         request/response shapes
    │   ├── service.py         the rules: save, submit, return, approve, reopen
    │   └── reconciliation.py  the worksheet math (pure, tested)
    ├── exports/       QuickBooks journal-entry CSV and other downloads
    │   └── journal_entry.py   worksheet -> balanced journal entry (pure, tested)
    └── settings/      QuickBooks account names, over/short alert
```

`router.py` = endpoints, `schemas.py` = data shapes, `service.py` = rules. Small modules keep their few SQL queries in the router; when a module grows rules, they move to `service.py`.

The web app mirrors this:

```
apps/web/src/
├── api/        client.ts (every API call in one place) + types.ts
├── auth/       AuthProvider: sign-in state, attaches the token to API calls
├── components/ small shared pieces (status chip, over/short gauge, paid-out lines)
├── lib/        money, dates, live reconciliation preview
└── pages/      one file per screen
```

## Roles

| Role | Can do |
| --- | --- |
| employee | Fill and submit worksheets for their assigned stores; edit while draft or sent back |
| manager | Same as employee, for all their stores (room to grow into first-pass review) |
| owner | Everything: review, approve, send back, reopen, export, people, stores, settings |

## Status workflow

```
draft ──submit──▶ submitted ──approve──▶ approved ──export──▶ exported
                   │     ▲                   │                   │
             send back   resubmit            └──── reopen ◀──────┘
                   ▼     │
                  returned
```

Every step is written to `audit_log` with who and when.

## Growing into separate services

The modules are already separated by feature and only meet through the database, so any of them can become its own service later without rewriting it. The planned next ones are:

- **services/ai**: scans a photo of the register report and returns the worksheet fields (fills `report_uploads`).
- **services/quickbooks**: posts approved days straight into QuickBooks Online through Intuit's API (fills `qb_txn_id`).

Each will be a small FastAPI app next to `services/api`, with its own Dockerfile, called by the API.

## Adding a feature

1. If it needs a table or column, add `database/migrations/00N_what.sql`.
2. Add `services/api/app/modules/<feature>/router.py` (+ `schemas.py`, + `service.py` if it has rules).
3. Plug the router into `app/main.py`.
4. Add the calls to `apps/web/src/api/client.ts` and a page in `apps/web/src/pages/`.
5. Add a test in `services/api/tests/`.
