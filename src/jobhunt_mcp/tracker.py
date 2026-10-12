"""Tracker logic. Every function returns a short sentence that sounds natural when Alexa reads it."""

from __future__ import annotations

import sqlite3
from datetime import date

from . import db
from .classify import KIND_TO_STATUS, classify, is_noise, matches_company, sender_parts
from .dates import parse_when, say_date
from .mail import MailProvider

# A reply can only move an application forward, never back (rejected/offer are final).
_RANK = {s: i for i, s in enumerate(db.STATUSES)}


def _plural(n: int, word: str) -> str:
    if n == 1:
        return f"{n} {word}"
    return f"{n} {word[:-1]}ies" if word.endswith("ly") else f"{n} {word}s"


def _join(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def _label(row: sqlite3.Row) -> str:
    return f"{row['company']} ({row['role']})" if row["role"] else row["company"]


def add_application(conn, company: str, role: str = "", source: str = "") -> str:
    company = company.strip()
    if not company:
        return "Which company did you apply to?"
    existing = db.find_application(conn, company)
    if existing and existing["company"].lower() == company.lower() and existing["role"].lower() == role.strip().lower():
        return f"You already have {_label(existing)} in your tracker."
    conn.execute(
        "INSERT INTO applications (company, role, source, status, applied_on, updated_on) VALUES (?,?,?,?,?,?)",
        (company, role.strip(), source.strip(), "applied", db.today_str(), db.now_str()),
    )
    return f"Added {company}{' for ' + role.strip() if role.strip() else ''}. You now track " \
           f"{_plural(conn.execute('SELECT COUNT(*) FROM applications').fetchone()[0], 'application')}."


def list_applications(conn, status: str = "") -> str:
    status = status.strip().lower()
    if status and status not in db.STATUSES:
        return f"I don't know the status '{status}'. Try one of: {_join(list(db.STATUSES))}."
    rows = conn.execute(
        "SELECT * FROM applications" + (" WHERE status = ?" if status else "") + " ORDER BY updated_on DESC, id DESC",
        (status,) if status else (),
    ).fetchall()
    if not rows:
        return f"You have no {status + ' ' if status else ''}applications yet."
    if status:
        names = [_label(r) for r in rows[:6]]
        more = f", and {len(rows) - 6} more" if len(rows) > 6 else ""
        return f"You have {_plural(len(rows), status + ' application')}: {_join(names)}{more}."
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    parts = [f"{n} {s}" for s, n in sorted(counts.items(), key=lambda kv: _RANK[kv[0]])]
    return f"You have {_plural(len(rows), 'application')}: {_join(parts)}."


def update_status(conn, company: str, status: str) -> str:
    status = status.strip().lower()
    if status not in db.STATUSES:
        return f"I don't know the status '{status}'. Try one of: {_join(list(db.STATUSES))}."
    app = db.find_application(conn, company)
    if not app:
        return f"I couldn't find an application for {company}."
    conn.execute("UPDATE applications SET status=?, updated_on=? WHERE id=?", (status, db.now_str(), app["id"]))
    return f"Marked {app['company']} as {status}."


def add_followup(conn, company: str, when: str, note: str = "", today: date | None = None) -> str:
    app = db.find_application(conn, company)
    if not app:
        return f"I couldn't find an application for {company}. Add it first."
    try:
        due = parse_when(when, today)
    except ValueError as e:
        return str(e)
    conn.execute(
        "INSERT INTO followups (application_id, due_on, note) VALUES (?,?,?)", (app["id"], due.isoformat(), note.strip())
    )
    return f"Okay, I'll remind you to follow up with {app['company']} {say_date(due, today)}."


def todays_followups(conn, today: date | None = None) -> str:
    today = today or date.today()
    rows = conn.execute(
        "SELECT f.id, f.due_on, f.note, a.company FROM followups f JOIN applications a ON a.id=f.application_id "
        "WHERE f.done=0 AND f.due_on <= ? ORDER BY f.due_on",
        (today.isoformat(),),
    ).fetchall()
    if not rows:
        upcoming = conn.execute(
            "SELECT f.due_on, a.company FROM followups f JOIN applications a ON a.id=f.application_id "
            "WHERE f.done=0 ORDER BY f.due_on LIMIT 1"
        ).fetchone()
        if upcoming:
            return (f"Nothing due today. Your next follow-up is {upcoming['company']} "
                    f"{say_date(date.fromisoformat(upcoming['due_on']), today)}.")
        return "You have no follow-ups scheduled."
    items = []
    for r in rows:
        overdue = " (overdue)" if r["due_on"] < today.isoformat() else ""
        items.append(r["company"] + overdue + (f", {r['note']}" if r["note"] else ""))
    return f"You have {_plural(len(rows), 'follow-up')} due: {_join(items)}."


def complete_followup(conn, company: str) -> str:
    app = db.find_application(conn, company)
    if not app:
        return f"I couldn't find an application for {company}."
    n = conn.execute("UPDATE followups SET done=1 WHERE application_id=? AND done=0", (app["id"],)).rowcount
    return f"Marked {_plural(n, 'follow-up')} with {app['company']} as done." if n else \
        f"You have no open follow-ups with {app['company']}."


def check_new_replies(conn, mail: MailProvider, days: int = 7) -> str:
    """Scan the inbox, match mail to tracked applications, update statuses, announce each reply once."""
    apps = conn.execute("SELECT * FROM applications").fetchall()
    if not apps:
        return "You aren't tracking any applications yet, so there's nothing to match replies to."
    for msg in mail.recent_messages(days):
        if is_noise(msg.sender) or conn.execute("SELECT 1 FROM replies WHERE message_id=?", (msg.id,)).fetchone():
            continue
        app = next((a for a in apps if matches_company(a["company"], msg.sender, msg.subject)), None)
        if not app:
            continue
        kind = classify(msg.subject, msg.body)
        conn.execute(
            "INSERT INTO replies (message_id, application_id, sender, subject, kind, received_on) VALUES (?,?,?,?,?,?)",
            (msg.id, app["id"], msg.sender, msg.subject, kind, msg.received_on),
        )
        new_status = KIND_TO_STATUS[kind]
        current = conn.execute("SELECT status FROM applications WHERE id=?", (app["id"],)).fetchone()["status"]
        if current not in ("offer", "rejected") and _RANK[new_status] > _RANK[current]:
            conn.execute("UPDATE applications SET status=?, updated_on=? WHERE id=?",
                         (new_status, db.now_str(), app["id"]))
    rows = conn.execute(
        "SELECT r.rowid AS rid, r.kind, a.company FROM replies r JOIN applications a ON a.id=r.application_id "
        "WHERE r.announced=0 ORDER BY r.received_on DESC"
    ).fetchall()
    if not rows:
        return "No new replies from companies."
    conn.execute("UPDATE replies SET announced=1 WHERE announced=0")
    phrases = {
        "interview": "wants to set up an interview",
        "assessment": "sent an assessment",
        "offer": "sent you an offer",
        "rejected": "said they're not moving forward",
        "other": "replied",
    }
    lines = [f"{r['company']} {phrases[r['kind']]}" for r in rows]
    return f"You have {_plural(len(rows), 'new reply')}. {_join(lines)}."
