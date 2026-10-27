import os
from contextlib import contextmanager

import psycopg2
import psycopg2.extras

# Required values have no defaults on purpose: a missing Secret should crash
# the pod at startup instead of silently trying postgres/postgres.
DB_HOST = os.environ["DB_HOST"]
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ["DB_NAME"]
DB_USER = os.environ["DB_USER"]
DB_PASSWORD = os.environ["DB_PASSWORD"]
# Use "require" on RDS; "prefer" is fine for local compose / kind
DB_SSLMODE = os.environ.get("DB_SSLMODE", "prefer")


def get_db():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        sslmode=DB_SSLMODE,
        connect_timeout=5,
    )


@contextmanager
def db_cursor():
    """Commit on success, roll back on error, and always close the connection."""
    conn = get_db()
    try:
        with conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                yield cur
    finally:
        conn.close()
