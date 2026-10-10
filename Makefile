# Gasolina: run the app from your terminal.
#
#   make            show this help
#   make demo       everything on this laptop with sample data; pick Owner or Employee to sign in
#   make live       screens on this laptop, real online API + database, real Google sign-in
#   make stop       stop the demo database and API
#   make reset-demo wipe the demo database and start fresh next time
#   make test       run the API tests (needs Python 3.10+)
#   make release    release test -> production screens: checks VERSION + CHANGELOG, tests, merge to main, tag
#
# Needs: Node 20+, and Docker Desktop (for `make demo`).

PYTHON ?= python3
VENV    = services/api/.venv

.PHONY: help demo live check-node check-docker stop reset-demo test release

help:
	@sed -n '2,10p' Makefile | sed 's/^# \{0,1\}//'

check-node:
	@command -v node >/dev/null || (echo "Missing Node.js: install the LTS version from https://nodejs.org" && exit 1)

check-docker:
	@command -v docker >/dev/null || (echo "Missing Docker: install Docker Desktop from https://www.docker.com/products/docker-desktop and open it" && exit 1)
	@docker info >/dev/null 2>&1 || (echo "Docker isn't running: open Docker Desktop, wait until it says Running, then try again" && exit 1)

apps/web/node_modules/.installed: apps/web/package.json
	@echo "Installing web app packages (first time takes a minute)..."
	@cd apps/web && npm install --silent
	@touch $@

# ---------- demo: database + API in Docker, screens on the laptop ----------
demo: check-node check-docker apps/web/node_modules/.installed
	@echo "Starting the demo database and API (first time builds the API, ~1-2 minutes)..."
	@docker compose up -d --build db api
	@echo "Waiting for the API..."
	@for i in $$(seq 1 90); do curl -sf http://localhost:8000/api/health >/dev/null && break; sleep 1; done
	@curl -sf http://localhost:8000/api/health >/dev/null || (echo "The API didn't start. See why with: docker compose logs api" && exit 1)
	@docker compose exec -T api python -m scripts.seed_demo owner@example.com
	@echo ""
	@echo "  Demo is ready:  open  http://localhost:5173"
	@echo "  Sign in by picking Owner or an Employee."
	@echo "  Play both roles: normal window = Owner, private/incognito window = Employee."
	@echo "  Press Ctrl+C here to stop."
	@echo ""
	@trap 'docker compose stop api >/dev/null 2>&1' EXIT INT TERM; \
	 cd apps/web && npx vite --mode demo --port 5173 --strictPort

# ---------- live: real API + Google sign-in ----------
live: check-node apps/web/node_modules/.installed
	@echo ""
	@echo "  Open  http://localhost:5173  and click Continue with Google."
	@echo "  Uses the real online API and database. The first click can take ~50 s while the free API wakes up."
	@echo "  Press Ctrl+C here to stop."
	@echo ""
	@cd apps/web && npx vite --mode live --port 5173 --strictPort

# ---------- housekeeping ----------
stop:
	@docker compose stop

reset-demo:
	@docker compose down -v
	@echo "Demo database wiped. Next 'make demo' starts fresh."

test:
	@$(PYTHON) -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' || (echo "make test needs Python 3.10+ (this Mac has $$($(PYTHON) --version)). Install from https://www.python.org/downloads/ or run: make test PYTHON=python3.12" && exit 1)
	@test -x $(VENV)/bin/python && $(VENV)/bin/python -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' || (rm -rf $(VENV) && cd services/api && $(PYTHON) -m venv .venv)
	@cd services/api && .venv/bin/pip install -q -r requirements-dev.txt && .venv/bin/python -m pytest -q

# ---------- release: test -> main, tag v<VERSION> (see docs/DEPLOY.md "Releasing") ----------
release:
	@bash deploy/release.sh
