"""SQLite store for applications, follow-ups and processed emails."""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path

STATUSES = ("applied", "replied", "assessment", "interview", "offer", "rejected")

SCHEMA = """
CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'applied',
    applied_on TEXT NOT NULL,
    updated_on TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS followups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL REFERENCES applications(id),
    due_on TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    done INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS replies (
    message_id TEXT PRIMARY KEY,
    application_id INTEGER REFERENCES applications(id),
    sender TEXT, subject TEXT, kind TEXT, received_on TEXT,
    announced INTEGER NOT NULL DEFAULT 0
);
"""


def db_path() -> str:
    return os.environ.get("JOBHUNT_DB", str(Path.home() / ".jobhunt-mcp" / "tracker.db"))


@contextmanager
def connect(path: str | None = None):
    path = path or db_path()
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def find_application(conn: sqlite3.Connection, company: str) -> sqlite3.Row | None:
    """Case-insensitive match: exact first, then substring ("zoho" finds "Zoho Corp")."""
    name = company.strip().lower()
    rows = conn.execute("SELECT * FROM applications ORDER BY updated_on DESC, id DESC").fetchall()
    for r in rows:
        if r["company"].lower() == name:
            return r
    for r in rows:
        if name and (name in r["company"].lower() or r["company"].lower() in name):
            return r
    return None


def today_str() -> str:
    return date.today().isoformat()


def now_str() -> str:
    return datetime.now().isoformat(timespec="seconds")
