"""Known-bad fixture: request input concatenated into SQL (CWE-89).

The test copies this tree to a temp dir and also writes a generated
GitHub-token-shaped string into config.py there, so no secret-shaped value is
ever committed to this repository.
"""
import sqlite3

from flask import Flask, request

app = Flask(__name__)


@app.route("/user")
def user():
    name = request.args.get("name")
    conn = sqlite3.connect("db.sqlite")
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM users WHERE name = '{name}'")
    return str(cur.fetchall())
