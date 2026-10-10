# Feature spec: admin Monitor (live traffic, who's online, usage, history)

_Status: **built Oct 10** (2026.10.5) · Bhajan, Oct 10: "I want it for the admin (me): live traffic, users connected, usage, along with the history". Not for the owner. $0._

## Problem
After a release we can't tell whether anyone has used the app, who is on it right now, whether requests are failing, or who changed what. The only answers today come from running SQL against the database (Supabase "last sign-in" is misleading: phones stay signed in for days), and the history log only shows on one worksheet at a time. People, store and settings changes weren't logged at all.

## Who
**App admin only** (people in `ADMIN_EMAILS`). Owner and co-owner never see the page or its data; the API refuses them (403). While the admin is using **View as**, the page is not available (switch back first).

## What the admin sees: one page, **Monitor** (nav item only for the admin)
Refreshes by itself every 15 seconds while the tab is open (paused when the tab is hidden).

1. **Online now**: everyone who used the app in the last 2 minutes: name, role, the screen they're on, phone or computer, last activity ("20 s ago"). Admin's own rows are hidden unless "Include me" is ticked.
2. **Traffic**: requests per minute for the last 60 minutes (small bar chart), and for the chosen period: requests, people, errors (5xx), slow requests (over 2 s).
3. **Usage** for a period (**Since last release** (default) · Today · 7 days · 30 days): per person: visits, active minutes, requests, screens used most, phone/computer, last seen. Per day: people, requests, errors. A list of the latest errors (when, who, what failed, status).
4. **History**: everything people did, newest first: worksheet steps (saved, submitted, sent back, approved, reopened, exported), vendors, purchases / expenses, balance sheet, **people, stores and settings** (new). Filter by person and by kind; "Show more".

## How it works
- **Request log.** Every API request (except `/api/health`, the 5-minute keep-warm, and browser pre-flight `OPTIONS`) writes one row after the answer has been sent: time, person (if signed in), View-as target, method, route (`/api/reports/{report_id}`, never ids or query values), screen (from the `X-Page` header the web app sends), status, milliseconds, device (phone / computer from the browser's user agent). No IP address, no request bodies, no money values.
- **Presence ping.** While the app is open and visible, the screens call `GET /api/me/ping` once a minute, so someone reading a page without clicking still shows as online. Pings count for "online" and "active minutes", not as traffic.
- **Visits** = a person's requests with less than 30 minutes between them. **Active minutes** = distinct minutes with at least one request or ping.
- **Never breaks the app.** If writing the log row fails, the request still succeeds (the error is printed to the server log).
- **Retention.** Request rows older than **90 days** are removed when the API starts. The history log (`audit_log`) is kept forever, as before.
- **Live** = polling every 15 s. No websockets: Cloud Run scales to zero and this is a handful of people.

## API (admin only; anyone else 403)
| Method | Path | Returns |
| --- | --- | --- |
| GET | `/api/me/ping` | `{ok: true}` (any signed-in person; marks them online) |
| GET | `/api/monitor/live?include_me=` | online now; requests per minute, last 60 minutes |
| GET | `/api/monitor/usage?period=release\|today\|7d\|30d&include_me=` | period start, totals, per person, per day, latest errors, slowest routes |
| GET | `/api/monitor/history?person_id=&kind=&before=&limit=` | history rows newest first (who, what, details, store / day for worksheets), `next_before` for "Show more" |

## Data
Migration **010** (add-only): `api_requests (id, at, person_id, viewed_as, method, route, page, status, ms, device)`, indexes on `at` and `(person_id, at)`, locked like every table (RLS on, no policies).
New history actions (`audit_log`, no schema change): `person.invited`, `person.changed`, `person.removed`, `store.added`, `store.changed`, `store.removed`, `settings.saved`, `test_data.reset`.

## Privacy
- The owner's staff are recorded when they use the app (when, which screen). This is ordinary for work software; the sign-in page says so in one line: "Use of this app is recorded (who, when, which screen) to keep it working."
- Only the app admin can see it. Nothing personal beyond name, role and device type is stored.

## Cost
$0: one small row per request in the existing Supabase database (≈ a few MB per month at this size), no new services.

## Acceptance
- [x] Only the admin gets the Monitor nav item and the `/api/monitor/*` data; owner, co-owner, manager, employee get 403; View as gets 403.
- [x] Every request except health/OPTIONS is logged with route template (no ids), screen, status, ms, device; failures to log never fail the request.
- [x] Ping marks a person online; online = last 2 minutes; admin hidden unless "Include me".
- [x] Usage since last release / today / 7 / 30 days: visits, active minutes, requests, top screens, errors.
- [x] History shows all kinds incl. people, stores, settings changes, with filters and paging.
- [x] Rows older than 90 days removed on start.
- [x] Tests (`tests/test_monitor.py`, 11), `npm run build`, click-through locally as employee (phone), co-owner, owner, admin (desktop + phone); docs (STATUS, ARCHITECTURE, CHANGELOG 2026.10.5).
- [ ] On the test site after the automatic deploy; then production (Deploy production button).

## Stories
1. Request log + ping + retention (API, migration 010).
2. History for people / stores / settings.
3. Monitor endpoints (live, usage, history).
4. Monitor page (web) + `X-Page` header + ping + sign-in line.
