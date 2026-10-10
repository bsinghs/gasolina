# Feature spec: automatic tests, release tags and API deploys (GitHub Actions)

_Status: **live Oct 9** · Bhajan, Oct 9: automate the git and deploy steps. $0 (GitHub Actions free tier, Cloud Build free minutes)_

## Problem
Tagging releases and deploying the API were manual steps on two machines (laptop for tags, Cloud Shell for `deploy.sh`). Easy to forget, easy to get out of order (screens on a new version, API on an old one).

## What happens now

| When | GitHub Actions does | File |
| --- | --- | --- |
| Any push (or pull request) to `test` or `main` | Runs **all API tests** (with a real Postgres 16) and **type-checks + builds** the web app. Red/green mark on the commit | `.github/workflows/ci.yml` |
| Push to `test`, tests green | **Deploys the API to the TEST copy** (`deploy.sh test` in CI mode) | `ci.yml` → `deploy-api.yml` |
| Push to `main`, tests green | **Tags the release `v<VERSION>`** if that tag doesn't exist yet (and checks `CHANGELOG.md` has the entry) | `ci.yml` (job `tag-release`) |
| You press **Deploy production** (GitHub → Actions → Deploy production → Run workflow, branch `main`) | Runs the tests again, then **deploys the API to PRODUCTION** | `.github/workflows/deploy-production.yml` |
| (unchanged) push to `test` / `main` | Cloudflare Pages publishes the screens | Cloudflare |

Production stays a **deliberate click** (never automatic on merge), so nothing reaches the real app by accident.

## Release flow (replaces the manual tag + Cloud Shell steps)
1. Change on `test` (with `VERSION` bump + `CHANGELOG.md` entry when it's a release) → push. Tests run; test API and test site update by themselves.
2. Try it on https://test.shift-close.pages.dev.
3. Move it to `main` (`make release`, or Claude does the same merge + push). Tests run, the tag `v<VERSION>` is created, the production screens publish.
4. **Deploy production** button for the API. Footer shows the same version for screens and API; Settings → Versions & releases records it.

`deploy.sh` still works by hand from Cloud Shell (backup, and for the one-time setup steps: secrets, keep-warm job, budget alert).

## How GitHub signs in to Google Cloud (no keys)
**Workload Identity Federation**: Google trusts GitHub's own sign-in token, **only for runs from `bsinghs/gasolina`**, and lets them act as one deploy account (`github-deployer@gasolina-510519`). No password or key file exists anywhere to leak.

The deploy account can only: build images (Cloud Build), store them (Artifact Registry), start them on Cloud Run as the existing runtime account, read build logs. It can't read the database secret (the running API does that).

One-time setup (Bhajan, Cloud Shell, ~5 minutes): `bash deploy/cloudrun/setup-github-deploy.sh`, then add the two values it prints as **repository variables** in GitHub (Settings → Secrets and variables → Actions → Variables): `GCP_WIF_PROVIDER`, `GCP_DEPLOY_SA`. Until they're set, the test auto-deploy is skipped (tests and tags still run).

## CI mode of deploy.sh
`CI=true` (set by the workflow): no confirmation question (the button is the confirmation), and only the build + start + health-check steps. `DEPLOYED_BY` = `github-actions (<GitHub user>)` in the release log. `PROJECT_NUMBER` is taken from `GCP_WIF_PROVIDER` (the deploy account isn't allowed to read project details). If a step fails, the failing line shows as an error note on the run.

## Acceptance
- [x] Workflows: tests + web build on every push; tag on main; test deploy on test; production deploy button (YAML checked).
- [x] `deploy.sh` CI mode; setup script for keyless sign-in; `make release` no longer tags by hand.
- [x] First green runs on GitHub (Oct 9: CI on `test` and `main`); `main` run tagged `v2026.10.4` by itself.
- [x] Setup script run + repository variables set (Bhajan, Oct 9).
- [x] First automatic test deploy (Oct 9, commit ba4eedb, health check green).
- [x] First production deploy by button (Oct 9, 11:34 PM, d9347ec): screens and API both 2026.10.4; release log row recorded.
