import os
import secrets
import string

import psycopg2
import psycopg2.errors
from flask import Flask, jsonify, redirect, render_template, request
from prometheus_flask_exporter import PrometheusMetrics

from db import db_cursor

app = Flask(__name__)
# group_by="url_rule" keeps the label as "/<code>" instead of one label per short code
metrics = PrometheusMetrics(app, group_by="url_rule")

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8080").rstrip("/")
CODE_LENGTH = int(os.environ.get("CODE_LENGTH", 6))
MAX_URL_LENGTH = 2048
MAX_CODE_ATTEMPTS = 5
ALPHABET = string.ascii_letters + string.digits


def generate_code(length=CODE_LENGTH):
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


@app.route("/health")
def health():
    # Liveness: no DB call, so a DB outage never restarts the pods
    return jsonify(status="ok"), 200


@app.route("/ready")
def ready():
    # Readiness: DB reachable and schema present
    try:
        with db_cursor() as cur:
            cur.execute("SELECT 1 FROM urls LIMIT 1")
    except psycopg2.Error:
        return jsonify(status="not ready"), 503
    return jsonify(status="ready"), 200


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/shorten", methods=["POST"])
def shorten():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        data = {}
    original_url = data.get("url")

    if not isinstance(original_url, str) or not original_url.strip():
        return jsonify(error="url is required"), 400
    original_url = original_url.strip()
    if len(original_url) > MAX_URL_LENGTH:
        return jsonify(error="url is too long"), 400
    if not original_url.startswith(("http://", "https://")):
        original_url = "https://" + original_url

    # The UNIQUE constraint is the real guard: insert, and retry on a collision
    for _ in range(MAX_CODE_ATTEMPTS):
        code = generate_code()
        try:
            with db_cursor() as cur:
                cur.execute(
                    "INSERT INTO urls (code, original_url) VALUES (%s, %s) "
                    "RETURNING code, original_url",
                    (code, original_url),
                )
                row = cur.fetchone()
        except psycopg2.errors.UniqueViolation:
            continue
        return (
            jsonify(
                short_url=f"{BASE_URL}/{row['code']}",
                code=row["code"],
                original_url=row["original_url"],
            ),
            201,
        )

    return jsonify(error="could not generate a unique code, please retry"), 503


@app.route("/<code>")
def redirect_to_original(code):
    with db_cursor() as cur:
        cur.execute(
            "UPDATE urls SET clicks = clicks + 1 WHERE code = %s "
            "RETURNING original_url",
            (code,),
        )
        row = cur.fetchone()

    if row is None:
        return jsonify(error="short URL not found"), 404
    return redirect(row["original_url"], code=302)


@app.route("/api/stats/<code>")
def stats(code):
    with db_cursor() as cur:
        cur.execute(
            "SELECT code, original_url, created_at, clicks FROM urls WHERE code = %s",
            (code,),
        )
        row = cur.fetchone()

    if row is None:
        return jsonify(error="short URL not found"), 404
    return jsonify(row), 200
