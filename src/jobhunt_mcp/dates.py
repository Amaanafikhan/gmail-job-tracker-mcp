"""Parse the loose dates people say out loud ("Friday", "tomorrow", "in 3 days")."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def parse_when(text: str, today: date | None = None) -> date:
    """Turn spoken-style text into a date. A bare weekday means its next occurrence."""
    today = today or date.today()
    t = text.strip().lower()
    if not t:
        raise ValueError("I need a day for the follow-up.")
    if t == "today":
        return today
    if t == "tomorrow":
        return today + timedelta(days=1)
    if t == "day after tomorrow":
        return today + timedelta(days=2)

    m = re.fullmatch(r"in (\d+) (day|days|week|weeks)", t)
    if m:
        n = int(m.group(1)) * (7 if m.group(2).startswith("week") else 1)
        return today + timedelta(days=n)

    m = re.fullmatch(r"(?:(next|this|on)\s+)?(" + "|".join(WEEKDAYS) + ")", t)
    if m:
        target = WEEKDAYS.index(m.group(2))
        ahead = (target - today.weekday()) % 7 or 7
        return today + timedelta(days=ahead)

    raw = text.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d %B %Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    for fmt in ("%d %B %Y", "%B %d %Y"):  # "30 October" / "October 30": assume the coming one
        try:
            d = datetime.strptime(f"{raw} {today.year}", fmt).date()
        except ValueError:
            continue
        return d if d >= today else d.replace(year=today.year + 1)
    raise ValueError(f"I couldn't understand the day '{text}'. Try 'Friday', 'tomorrow' or a date.")


def say_date(d: date, today: date | None = None) -> str:
    """Natural spoken form of a date."""
    today = today or date.today()
    delta = (d - today).days
    if delta == 0:
        return "today"
    if delta == 1:
        return "tomorrow"
    if 1 < delta < 7:
        return d.strftime("%A")
    if delta == -1:
        return "yesterday"
    return d.strftime("%A, %B ") + str(d.day)
