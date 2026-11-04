"""User search endpoint. Seeded defects for the review evals: do not fix."""
import sqlite3

from flask import Flask, request

app = Flask(__name__)


def get_db():
    return sqlite3.connect("app.db")


@app.route("/search")
def search():
    q = request.args.get("q", "")
    cur = get_db().cursor()
    # SEEDED: CWE-89 SQL injection (user input interpolated into SQL).
    cur.execute(f"SELECT id, name FROM users WHERE name LIKE '%{q}%'")
    return {"users": cur.fetchall()}
