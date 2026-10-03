# Gasolina: run the app from your terminal.
#
#   make            show this help
#   make demo       everything on this laptop with sample data; pick Owner or Employee to sign in
#   make live       screens on this laptop, real online API + database, real Google sign-in
#   make stop       stop the demo database
#   make reset-demo wipe the demo database and start fresh next time
#   make test       run the API tests
#
# Needs: Python 3.11+, Node 20+, and Docker Desktop (for `make demo` only).

PYTHON     ?= python3
USE_DOCKER ?= 1
DEMO_DB    ?= postgresql://postgres:postgres@localhost:5432/gasolina
API_ENV     = DATABASE_URL=$(DEMO_DB) AUTH_MODE=dev BOOTSTRAP_OWNER_EMAIL=owner@example.com BOOTSTRAP_OWNER_NAME=Owner CORS_ORIGINS=http://localhost:5173
VENV        = services/api/.venv

.PHONY: help demo live setup check demo-db stop reset-demo test

help:
	@sed -n '2,10p' Makefile | sed 's/^# \{0,1\}//'

# ---------- one-time installs (skipped when already done) ----------
setup: check $(VENV)/.installed apps/web/node_modules/.installed

check:
	@command -v $(PYTHON) >/dev/null || (echo "Missing Python 3: install from https://www.python.org/downloads/" && exit 1)
	@command -v node >/dev/null || (echo "Missing Node.js: install the LTS version from https://nodejs.org" && exit 1)

$(VENV)/.installed: services/api/requirements.txt services/api/requirements-dev.txt
	@echo "Installing API packages (first time takes a minute)..."
	@cd services/api && $(PYTHON) -m venv .venv && .venv/bin/pip install -q --upgrade pip && .venv/bin/pip install -q -r requirements-dev.txt
	@touch $@

apps/web/node_modules/.installed: apps/web/package.json
	@echo "Installing web app packages (first time takes a minute)..."
	@cd apps/web && npm install --silent
	@touch $@

# ---------- demo: all local ----------
demo-db:
ifeq ($(USE_DOCKER),1)
	@command -v docker >/dev/null || (echo "Missing Docker: install Docker Desktop from https://www.docker.com/products/docker-desktop and open it" && exit 1)
	@docker info >/dev/null 2>&1 || (echo "Docker isn't running: open Docker Desktop, wait until it says Running, then try again" && exit 1)
	@docker compose up -d db >/dev/null
	@echo "Waiting for the demo database..."
	@for i in $$(seq 1 30); do docker compose exec -T db pg_isready -U postgres >/dev/null 2>&1 && break; sleep 1; done
endif

demo: setup demo-db
	@cd services/api && $(API_ENV) .venv/bin/python -m scripts.migrate
	@cd services/api && $(API_ENV) .venv/bin/python -m scripts.seed_demo owner@example.com
	@echo ""
	@echo "  Demo is starting:  open  http://localhost:5173"
	@echo "  Sign in by picking Owner or an Employee."
	@echo "  Play both roles: normal window = Owner, private/incognito window = Employee."
	@echo "  Press Ctrl+C here to stop."
	@echo ""
	@cd services/api && ($(API_ENV) .venv/bin/uvicorn app.main:app --port 8000 --log-level warning & echo $$! > /tmp/gasolina-api.pid)
	@trap 'kill $$(cat /tmp/gasolina-api.pid) 2>/dev/null; rm -f /tmp/gasolina-api.pid' EXIT INT TERM; \
	 cd apps/web && npx vite --mode demo --port 5173 --strictPort

# ---------- live: real API + Google sign-in ----------
live: check apps/web/node_modules/.installed
	@echo ""
	@echo "  Open  http://localhost:5173  and click Continue with Google."
	@echo "  Uses the real online API and database. The first click can take ~50 s while the free API wakes up."
	@echo "  Press Ctrl+C here to stop."
	@echo ""
	@cd apps/web && npx vite --mode live --port 5173 --strictPort

# ---------- housekeeping ----------
stop:
	@-kill $$(cat /tmp/gasolina-api.pid 2>/dev/null) 2>/dev/null; rm -f /tmp/gasolina-api.pid
ifeq ($(USE_DOCKER),1)
	@docker compose stop db
endif

reset-demo:
	@docker compose down -v
	@echo "Demo database wiped. Next 'make demo' starts fresh."

test: setup
	@cd services/api && .venv/bin/python -m pytest -q
