"""Classify recruiter emails and match them to tracked applications."""

from __future__ import annotations

import re
from email.utils import parseaddr

# Checked in order: the first matching kind wins, so the strongest signals come first.
RULES: list[tuple[str, tuple[str, ...]]] = [
    ("offer", ("offer letter", "pleased to offer", "we are happy to offer", "job offer")),
    ("rejected", (
        "unfortunately", "not moving forward", "will not be moving", "regret to inform",
        "other candidates", "not selected", "decided not to proceed",
    )),
    ("interview", (
        "interview", "schedule a call", "schedule a chat", "meet with", "discussion round",
        "technical round", "hr round",
    )),
    ("assessment", ("assessment", "coding test", "take-home", "hackerrank", "codility", "assignment")),
]

KIND_TO_STATUS = {
    "offer": "offer",
    "rejected": "rejected",
    "interview": "interview",
    "assessment": "assessment",
    "other": "replied",
}

# Mail from job boards / no-reply systems is not a human reply about an application.
NOISE_SENDERS = ("noreply", "no-reply", "donotreply", "newsletter", "jobalerts", "alerts@")


def classify(subject: str, body: str) -> str:
    text = f"{subject}\n{body}".lower()
    for kind, needles in RULES:
        if any(n in text for n in needles):
            return kind
    return "other"


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def sender_parts(sender: str) -> tuple[str, str]:
    """Return (display name, domain label) e.g. ("Zoho Recruiting", "zoho")."""
    name, addr = parseaddr(sender)
    domain = addr.split("@")[-1].lower() if "@" in addr else ""
    labels = domain.split(".")
    # "careers.zoho.com" -> "zoho"; "zoho.co.in" -> "zoho"
    skip = {"com", "co", "in", "org", "net", "io", "careers", "jobs", "mail", "mails", "hr", "talent"}
    core = next((p for p in labels if p and p not in skip), labels[0] if labels else "")
    return name, core


def is_noise(sender: str) -> bool:
    _, addr = parseaddr(sender)
    return any(n in addr.lower() for n in NOISE_SENDERS)


def matches_company(company: str, sender: str, subject: str) -> bool:
    c = _norm(company)
    if len(c) < 2:
        return False
    name, domain = sender_parts(sender)
    d = _norm(domain)
    return (
        c in d
        or (len(d) >= 3 and d in c)  # company "Zoho Corp" vs domain "zoho"
        or c in _norm(name)
        or c in _norm(subject)
    )
