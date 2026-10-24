"""Known-good fixture: the same handler with a parameterised query."""
import sqlite3

from flask import Flask, request

app = Flask(__name__)


@app.route("/user")
def user():
    name = request.args.get("name", "")
    conn = sqlite3.connect("db.sqlite")
    rows = conn.execute("SELECT id FROM users WHERE name = ?", (name,)).fetchall()
    return {"ids": [row[0] for row in rows]}
