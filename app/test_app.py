from contextlib import contextmanager
from datetime import datetime

import psycopg2
import psycopg2.errors
import pytest

import main


class FakeCursor:
    """Tiny in-memory stand-in for the urls table, so CI needs no Postgres."""

    def __init__(self, store):
        self.store = store
        self._row = None

    def execute(self, sql, params=()):
        s = " ".join(sql.split()).upper()
        if s.startswith("INSERT"):
            code, url = params
            if code in self.store:
                raise psycopg2.errors.UniqueViolation()
            row = {
                "code": code,
                "original_url": url,
                "created_at": datetime(2026, 1, 1),
                "clicks": 0,
            }
            self.store[code] = row
            self._row = row
        elif s.startswith("UPDATE"):
            row = self.store.get(params[0])
            if row:
                row["clicks"] += 1
            self._row = {"original_url": row["original_url"]} if row else None
        elif s.startswith("SELECT CODE"):
            self._row = self.store.get(params[0])
        else:  # SELECT 1 FROM urls LIMIT 1
            self._row = {"?column?": 1}

    def fetchone(self):
        return self._row


@pytest.fixture
def env(monkeypatch):
    store = {}

    @contextmanager
    def fake_cursor():
        yield FakeCursor(store)

    monkeypatch.setattr(main, "db_cursor", fake_cursor)
    return main.app.test_client(), store


def test_health_needs_no_db(monkeypatch):
    def boom():
        raise AssertionError("/health must not touch the DB")

    monkeypatch.setattr(main, "db_cursor", boom)
    assert main.app.test_client().get("/health").status_code == 200


def test_ready_ok(env):
    client, _ = env
    assert client.get("/ready").status_code == 200


def test_ready_503_when_db_down(monkeypatch):
    @contextmanager
    def down():
        raise psycopg2.OperationalError("db down")
        yield

    monkeypatch.setattr(main, "db_cursor", down)
    assert main.app.test_client().get("/ready").status_code == 503


@pytest.mark.parametrize("payload", [{}, {"url": ""}, {"url": 5}, {"url": "   "}, [1, 2]])
def test_shorten_rejects_bad_input(env, payload):
    client, _ = env
    assert client.post("/api/shorten", json=payload).status_code == 400


def test_shorten_creates_code_and_adds_scheme(env):
    client, store = env
    resp = client.post("/api/shorten", json={"url": "example.com"})
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["original_url"] == "https://example.com"
    assert body["short_url"].endswith("/" + body["code"])
    assert body["code"] in store


def test_shorten_retries_on_collision(env, monkeypatch):
    client, store = env
    store["aaaaaa"] = {"code": "aaaaaa", "original_url": "https://old.com", "clicks": 0}
    codes = iter(["aaaaaa", "bbbbbb"])
    monkeypatch.setattr(main, "generate_code", lambda: next(codes))
    resp = client.post("/api/shorten", json={"url": "https://new.com"})
    assert resp.status_code == 201
    assert resp.get_json()["code"] == "bbbbbb"


def test_redirect_known_code(env):
    client, store = env
    store["abc123"] = {"code": "abc123", "original_url": "https://example.com", "clicks": 0}
    resp = client.get("/abc123")
    assert resp.status_code == 302
    assert resp.headers["Location"] == "https://example.com"
    assert store["abc123"]["clicks"] == 1


def test_redirect_unknown_code_404(env):
    client, _ = env
    assert client.get("/nope").status_code == 404


def test_stats_unknown_code_404(env):
    client, _ = env
    assert client.get("/api/stats/nope").status_code == 404
