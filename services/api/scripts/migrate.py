"""Apply database/migrations/*.sql in order, skipping ones already applied.

    python -m scripts.migrate
"""

from pathlib import Path

import psycopg

from app.core.config import get_settings

MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "database" / "migrations"


def main() -> None:
    with psycopg.connect(get_settings().database_url, autocommit=True) as conn:
        conn.execute(
            "create table if not exists schema_migrations (version text primary key, applied_at timestamptz default now())"
        )
        done = {row[0] for row in conn.execute("select version from schema_migrations")}
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if path.name in done:
                continue
            print(f"applying {path.name}")
            with conn.transaction():
                conn.execute(path.read_text())
                conn.execute("insert into schema_migrations (version) values (%s)", [path.name])
    print("database is up to date")


if __name__ == "__main__":
    main()
