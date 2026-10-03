# Gasolina · Shift Close

Employees submit each store's **daily sales worksheet** from their phone. The owner **reviews, approves or sends back**, then **exports approved days to QuickBooks** as journal entries.

![System architecture](docs/diagrams/1-architecture.png)

**Start here:** [where we are and what's next](docs/STATUS.md) · [architecture and diagrams](docs/ARCHITECTURE.md) · [deploy checklist](docs/DEPLOY.md)

```
gasolina/
├── apps/
│   └── web/            React web app (what people see). Talks only to the API.
├── services/
│   └── api/            Python API (FastAPI). All business rules and database access.
├── database/
│   └── migrations/     Plain SQL that creates and changes the tables
├── docs/
│   ├── STATUS.md       What's done, what's next
│   ├── ARCHITECTURE.md How the pieces fit (with diagrams) and how to add a feature
│   ├── DEPLOY.md       Step-by-step: Supabase, Google sign-in, hosting
│   └── diagrams/       Diagram sources (.mmd) and images (.png)
└── docker-compose.yml  Local Postgres + API for `make demo`
```

## Run it on your computer

Quickest: `make demo` (everything local, sign in by picking Owner or Employee) or `make live` (real online API + Google sign-in). Run `make` to see all commands. `make demo` runs the database and API in Docker, so it only needs Node 20+ and Docker Desktop.

Manual steps, if you'd rather:

You need Python 3.10+ (macOS's built-in 3.9 is too old), Node 20+, and Docker (or any Postgres 15+).

```bash
# 1. Database
docker compose up -d db

# 2. API  (http://localhost:8000/docs shows every endpoint)
cd services/api
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env                      # AUTH_MODE=dev is fine locally
python -m scripts.migrate
python -m scripts.seed_demo you@gmail.com # 2 stores, you as owner, 2 test employees
uvicorn app.main:app --reload

# 3. Web app (new terminal)  ->  http://localhost:5173
cd apps/web
npm install
cp .env.example .env.local                # VITE_AUTH_MODE=dev
npm run dev
```

In dev mode you sign in by typing an email: `you@gmail.com` (owner), `employee1@example.com` or `employee2@example.com`.

## Tests

```bash
cd services/api
pytest                                                      # math + QuickBooks entry
TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/gasolina_test pytest   # + full workflow
```

The test database is wiped on every run, so point it at a database used only for tests.
