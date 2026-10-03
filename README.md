# Gasolina · Shift Close

Employees submit each store's **daily sales worksheet** from their phone. The owner **reviews, approves or sends back**, then **exports approved days to QuickBooks** as journal entries.

```
gasolina/
├── apps/
│   └── web/            React web app (what people see). Talks only to the API.
├── services/
│   └── api/            Python API (FastAPI). All business rules and database access.
├── database/
│   └── migrations/     Plain SQL that creates and changes the tables
├── docs/
│   ├── ARCHITECTURE.md How the pieces fit and how to add a feature
│   └── DEPLOY.md       Step-by-step: Supabase, Google sign-in, hosting
└── docker-compose.yml  Local Postgres for development
```

## Run it on your computer

You need Python 3.11+, Node 20+, and Docker (or any Postgres 15+).

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
