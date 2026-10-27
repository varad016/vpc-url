"""Create the schema once. Run before the app starts:
  - docker compose: one-shot command / service
  - Kubernetes: Helm pre-install/pre-upgrade hook Job
"""
import sys
import time

import psycopg2

from db import db_cursor

SCHEMA = """
CREATE TABLE IF NOT EXISTS urls (
    id SERIAL PRIMARY KEY,
    code VARCHAR(16) UNIQUE NOT NULL,
    original_url TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    clicks INTEGER DEFAULT 0
);
"""


def main(attempts=20, delay=3):
    for i in range(1, attempts + 1):
        try:
            with db_cursor() as cur:
                cur.execute(SCHEMA)
            print("schema ready", flush=True)
            return 0
        except psycopg2.OperationalError as exc:
            print(f"db not ready ({i}/{attempts}): {exc}", flush=True)
            time.sleep(delay)
    print("could not connect to the database, giving up", file=sys.stderr, flush=True)
    return 1


if __name__ == "__main__":
    sys.exit(main())
