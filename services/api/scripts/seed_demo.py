"""Add demo data: two stores, an owner, two employees.

    python -m scripts.seed_demo you@gmail.com
"""

import sys

import psycopg

from app.core.config import get_settings

STORES = ["Route 9 Fuel & Mart", "Main Street Gas"]
EMPLOYEES = [("employee1@example.com", "Jordan Ramos", 0), ("employee2@example.com", "Asha Patel", 1)]


def main(owner_email: str) -> None:
    with psycopg.connect(get_settings().database_url) as conn:
        store_ids = []
        for name in STORES:
            row = conn.execute(
                "insert into stores (name) values (%s) on conflict (name) do update set name = excluded.name returning id",
                [name],
            ).fetchone()
            store_ids.append(row[0])
        conn.execute(
            "insert into people (email, name, role) values (%s, 'Owner', 'owner') on conflict (lower(email)) do nothing",
            [owner_email],
        )
        for email, name, store_index in EMPLOYEES:
            person = conn.execute(
                """insert into people (email, name, role) values (%s, %s, 'employee')
                   on conflict (lower(email)) do update set name = excluded.name returning id""",
                [email, name],
            ).fetchone()
            conn.execute(
                "insert into store_members (person_id, store_id) values (%s, %s) on conflict do nothing",
                [person[0], store_ids[store_index]],
            )
    print(f"seeded {len(STORES)} stores, owner {owner_email}, {len(EMPLOYEES)} employees")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python -m scripts.seed_demo OWNER_EMAIL")
    main(sys.argv[1])
