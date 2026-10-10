# Feature spec: versions, changelog and release log

_Status: **built Oct 9** · Bhajan, Oct 9: "keep track and maintain best practice", simple and $0_

## Problem
Changes go to test, then production, but nothing says **which version** is running, **what changed** in it, or **when** it went live. When the owner reports a problem we can't quickly tell which code he's on.

## What we do (four simple pieces)

| # | Piece | How |
| --- | --- | --- |
| 1 | **Version number** | One file, `VERSION` (e.g. `2026.10.3` = year.month.release-in-month). Bumped once per production release. Each release gets a git tag `v2026.10.3` (made by `make release`), so we can always see or roll back exactly what shipped |
| 2 | **Changelog** | `CHANGELOG.md`: one short, plain-language entry per release, newest first ("Co-owners can see everything but not change it"). Written for the owner and us, not a list of commits |
| 3 | **What's running** | `GET /api/health` returns `version` and `commit`. The app shows the screens' and the API's version small at the bottom of every page. Settings shows both plus the release log |
| 4 | **Release log** | Every time an API starts with a new version or commit, it writes one row to the `releases` table: environment (test / production), version, commit, who deployed, when. So "what was released when" is recorded automatically; each copy (test, production) keeps its own log in its own database. Settings → Versions & releases lists it (owner, co-owner, admin) |

Not now (agreed): **feature switches** (turn a feature on per store / person). The test site is our trial area; add switches only when a feature needs a gradual start.

## Release steps (in DEPLOY.md)
1. Work on `test`; when ready, set `VERSION` and add the `CHANGELOG.md` entry (same commit).
2. Try it on the test site (`deploy.sh test` if the API changed).
3. `make release`: checks `VERSION` has a changelog entry and the tests pass, merges `test` into `main`, tags `v<VERSION>`, pushes (the screens publish).
4. `deploy.sh production` (Cloud Shell): builds the API with the version and commit; on start the API records the release.

## Data
Migration 009 (add-only): `releases (id, env, version, git_commit, deployed_by, started_at)`, locked like every table (RLS on, no policies). A row is added only when the version or commit differs from the last row for that environment (Cloud Run restarts often; those don't count).

## API
| Method | Path | Who | Returns |
| --- | --- | --- | --- |
| GET | `/api/health` | anyone | `{ok, env, version, commit}` |
| GET | `/api/releases` | owner, co-owner, admin | last 50 rows of this copy's release log, newest first |

Version and commit come from the `VERSION` file (copied into the API image) and `GIT_COMMIT` / `DEPLOYED_BY` (set by `deploy.sh`). Locally: `dev` / your git commit if set.

## Screens
- Footer on every page: `Shift Close 2026.10.3 · screens a1b2c3d · API 2026.10.3`. If screens and API versions differ, it's shown in amber (one of them hasn't been deployed yet).
- Settings → **Versions & releases**: running versions + the release log table.

## Acceptance
- [x] `VERSION`, `CHANGELOG.md` (history back to the first live release, Oct 4), tags for past releases.
- [x] Health shows version and commit; API records one release row per new version/commit per environment (tested: restart doesn't add a row).
- [x] Footer and Settings show versions; release log visible to owner / co-owner / admin only.
- [x] `make release` refuses when `VERSION` has no changelog entry.
