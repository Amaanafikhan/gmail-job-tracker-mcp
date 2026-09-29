"""
Daily Python Developer / Django Full Stack Developer job alerts for freshers.

Pulls jobs from free job APIs, keeps only fresher-friendly Python Developer and
Django (full stack) Developer roles in Bengaluru, Hyderabad or remote (open to
India), drops expired and old postings, removes jobs already sent, and delivers
a digest with salary, posting date and closing date to Telegram and/or Gmail.

Runs on GitHub Actions every morning. No paid services needed.
"""

import json
import os
import re
import smtplib
import sys
import time
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape

import requests

# ---------------------------------------------------------------------------
# Settings you may want to tweak
# ---------------------------------------------------------------------------

SEARCH_TERMS = [
    "python developer",
    "python fresher",
    "django developer",
    "django full stack developer",
    "python full stack developer",
]
CITIES = ["Bangalore", "Hyderabad"]
CITY_ALIASES = ["bangalore", "bengaluru", "hyderabad", "secunderabad"]

MAX_AGE_DAYS = 14         # drop anything posted more than this many days ago
SEEN_FILE = "seen_jobs.json"
SEEN_KEEP_DAYS = 45       # forget sent jobs after this many days

IST = timezone(timedelta(hours=5, minutes=30))

# --- Which job titles count -------------------------------------------------
# Title must mention Python or Django ...
TITLE_TECH = ["python", "django"]
# ... AND be a developer role ...
TITLE_ROLE = ["developer", "engineer", "programmer", "sde", "full stack",
              "fullstack", "full-stack", "backend", "back end", "back-end"]
# ... AND must NOT be one of these other job types.
TITLE_EXCLUDE = [
    "data scien", "data analy", "data engineer", "analyst", "machine learning",
    "ml ", " ml", "ai engineer", "ai/ml", "deep learning", "nlp", "computer vision",
    "qa", "quality", "test", "tester", "sdet", "automation test", "selenium",
    "devops", "sre", "cloud engineer", "support", "trainer", "faculty",
    "teacher", "tutor", "instructor", "mentor", "sales", "recruit", "hr ",
]

# Title words that mean "not a fresher role"
SENIOR_TITLE_WORDS = [
    "senior", "sr.", "sr ", "lead", "principal", "architect", "manager",
    "staff", "head", "director", "vp ", "expert", "iii",
]

# Words that show a role is fresher-friendly
FRESHER_WORDS = [
    "fresher", "freshers", "entry level", "entry-level", "junior", "jr.",
    "graduate", "trainee", "intern", "0-1 year", "0 - 1 year", "0-1 yrs",
    "0 to 1 year", "0-2 year", "0 - 2 year", "0-2 yrs", "early career",
    "associate software", "campus",
]

# Remote jobs are kept only if open to one of these
REMOTE_OK_REGIONS = ["india", "worldwide", "anywhere", "asia", "apac", "global"]

HEADERS = {"User-Agent": "daily-job-alerts/1.0 (personal job digest)"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def clean(text):
    """Strip HTML tags and extra spaces."""
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", text).strip()


def parse_date(value):
    """Turn the many date formats the job sites use into a UTC datetime."""
    if value in (None, "", 0):
        return None
    try:
        if isinstance(value, (int, float)):
            if value > 1e12:          # milliseconds
                value = value / 1000
            return datetime.fromtimestamp(value, tz=timezone.utc)
        s = str(value).strip().replace("Z", "+00:00")
        s = re.sub(r"(\.\d{6})\d+", r"\1", s)   # trim extra fraction digits
        dt = datetime.fromisoformat(s)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (ValueError, OSError, OverflowError):
        return None


def fmt_date(dt):
    return dt.astimezone(IST).strftime("%d %b") if dt else None


def fmt_inr_lpa(lo, hi, estimated=False):
    """Adzuna gives yearly INR numbers. Show them as LPA (lakhs per annum)."""
    def lpa(v):
        n = round(float(v) / 100000, 1)
        return f"{n:g}"
    try:
        lo = float(lo) if lo else None
        hi = float(hi) if hi else None
    except (TypeError, ValueError):
        return None
    if not lo and not hi:
        return None
    if lo and hi and round(lo, -4) != round(hi, -4):
        text = f"₹{lpa(lo)}–{lpa(hi)} LPA"
    else:
        text = f"₹{lpa(lo or hi)} LPA"
    return text + (" (est.)" if estimated else "")


def fmt_other_salary(lo, hi, currency):
    """For remote jobs paid in USD/EUR etc."""
    try:
        lo = int(lo) if lo else None
        hi = int(hi) if hi else None
    except (TypeError, ValueError):
        return None
    if not lo and not hi:
        return None
    sym = {"USD": "$", "EUR": "€", "GBP": "£", "INR": "₹"}.get((currency or "").upper(),
                                                               (currency or "") + " ")
    k = lambda v: f"{round(v / 1000)}k"
    return f"{sym}{k(lo)}–{k(hi)}/yr" if lo and hi and lo != hi else f"{sym}{k(lo or hi)}/yr"


def min_years_required(text):
    """
    Return the smallest 'years of experience' number found, or None.
    Handles '2+ years', '3-5 years', '2 to 4 yrs', 'minimum 2 years'.
    """
    text = text.lower()
    pattern = r"(\d{1,2})\s*(?:\+|plus)?\s*(?:-|–|to)?\s*(\d{1,2})?\s*\+?\s*(?:years|year|yrs|yr)"
    found = [int(m.group(1)) for m in re.finditer(pattern, text)]
    return min(found) if found else None


def title_ok(title):
    """Only Python Developer and Django (full stack) Developer style titles."""
    t = f" {title.lower()} "
    if not any(w in t for w in TITLE_TECH):
        return False
    if not any(w in t for w in TITLE_ROLE):
        return False
    if any(w in t for w in TITLE_EXCLUDE):
        return False
    return True


def classify(job):
    """
    Decide if a job fits. Returns a label or None to drop it.
      'fresher'   - clearly says fresher / junior / 0-1 years
      'unstated'  - no experience mentioned (worth a look)
      None        - not a fit
    """
    title = job["title"].lower()
    if not title_ok(title):
        return None
    if any(w in f" {title} " for w in SENIOR_TITLE_WORDS):
        return None

    blob = f"{title} {job['description'].lower()}"
    fresher = any(w in blob for w in FRESHER_WORDS)
    years = min_years_required(blob)

    if years is not None and years >= 2 and not fresher:
        return None
    if fresher or (years is not None and years <= 1):
        return "fresher"
    return "unstated"


def location_ok(job):
    loc = job["location"].lower()
    if job.get("remote"):
        return any(r in loc for r in REMOTE_OK_REGIONS) or loc == ""
    return any(c in loc for c in CITY_ALIASES)


def still_open(job, now):
    """Drop jobs whose closing date has passed or that are too old."""
    if job.get("closes") and job["closes"] < now:
        return False
    if job.get("posted") and job["posted"] < now - timedelta(days=MAX_AGE_DAYS):
        return False
    return True


def get_json(method, url, **kwargs):
    try:
        r = requests.request(method, url, headers=HEADERS, timeout=30, **kwargs)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"  ! {url.split('?')[0]} failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Job sources
# ---------------------------------------------------------------------------

def from_adzuna():
    app_id = os.getenv("ADZUNA_APP_ID")
    app_key = os.getenv("ADZUNA_APP_KEY")
    if not (app_id and app_key):
        print("- Adzuna: skipped (no keys)")
        return []
    jobs = []
    for term in SEARCH_TERMS:
        for city in CITIES:
            data = get_json(
                "GET",
                "https://api.adzuna.com/v1/api/jobs/in/search/1",
                params={
                    "app_id": app_id, "app_key": app_key,
                    "what": term, "where": city,
                    "max_days_old": MAX_AGE_DAYS,
                    "results_per_page": 50, "content-type": "application/json",
                },
            )
            for j in (data or {}).get("results", []):
                jobs.append({
                    "id": f"adzuna-{j.get('id')}",
                    "title": clean(j.get("title")),
                    "company": (j.get("company") or {}).get("display_name", ""),
                    "location": (j.get("location") or {}).get("display_name", city),
                    "description": clean(j.get("description")),
                    "url": j.get("redirect_url", ""),
                    "source": "Adzuna",
                    "remote": False,
                    "salary": fmt_inr_lpa(j.get("salary_min"), j.get("salary_max"),
                                          str(j.get("salary_is_predicted")) == "1"),
                    "posted": parse_date(j.get("created")),
                    "closes": None,
                })
            time.sleep(1)
    print(f"- Adzuna: {len(jobs)} raw")
    return jobs


def from_jooble():
    key = os.getenv("JOOBLE_API_KEY")
    if not key:
        print("- Jooble: skipped (no key)")
        return []
    since = (datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)).strftime("%Y-%m-%d")
    jobs = []
    for term in SEARCH_TERMS:
        for city in CITIES:
            data = get_json(
                "POST", f"https://jooble.org/api/{key}",
                json={"keywords": term, "location": f"{city}, India",
                      "page": 1, "datecreatedfrom": since},
            )
            for j in (data or {}).get("jobs", []):
                jobs.append({
                    "id": f"jooble-{j.get('id')}",
                    "title": clean(j.get("title")),
                    "company": j.get("company", ""),
                    "location": j.get("location", city),
                    "description": clean(j.get("snippet")),
                    "url": j.get("link", ""),
                    "source": "Jooble",
                    "remote": False,
                    "salary": clean(j.get("salary")) or None,
                    "posted": parse_date(j.get("updated")),
                    "closes": None,
                })
            time.sleep(1)
    print(f"- Jooble: {len(jobs)} raw")
    return jobs


def from_remotive():
    jobs = []
    for term in ["python", "django"]:
        data = get_json("GET", "https://remotive.com/api/remote-jobs",
                        params={"search": term, "limit": 100})
        for j in (data or {}).get("jobs", []):
            jobs.append({
                "id": f"remotive-{j.get('id')}",
                "title": clean(j.get("title")),
                "company": j.get("company_name", ""),
                "location": j.get("candidate_required_location", ""),
                "description": clean(j.get("description"))[:3000],
                "url": j.get("url", ""),
                "source": "Remotive",
                "remote": True,
                "salary": clean(j.get("salary")) or None,
                "posted": parse_date(j.get("publication_date")),
                "closes": None,
            })
    print(f"- Remotive: {len(jobs)} raw")
    return jobs


def from_himalayas():
    jobs = []
    data = get_json("GET", "https://himalayas.app/jobs/api", params={"limit": 100})
    for j in (data or {}).get("jobs", []):
        restrictions = j.get("locationRestrictions") or []
        seniority = " ".join(j.get("seniority") or []).lower()
        if seniority and not any(s in seniority for s in ["entry", "junior", "intern"]):
            continue
        jobs.append({
            "id": f"himalayas-{j.get('guid') or j.get('applicationLink')}",
            "title": clean(j.get("title")),
            "company": j.get("companyName", ""),
            "location": ", ".join(restrictions) if restrictions else "Worldwide",
            "description": clean(j.get("description") or j.get("excerpt"))[:3000],
            "url": j.get("applicationLink", ""),
            "source": "Himalayas",
            "remote": True,
            "salary": fmt_other_salary(j.get("minSalary"), j.get("maxSalary"),
                                       j.get("currency")),
            "posted": parse_date(j.get("pubDate")),
            "closes": parse_date(j.get("expiryDate")),
        })
    print(f"- Himalayas: {len(jobs)} raw")
    return jobs


# ---------------------------------------------------------------------------
# Remember what was already sent
# ---------------------------------------------------------------------------

def load_seen():
    try:
        with open(SEEN_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_seen(seen):
    cutoff = (datetime.now(timezone.utc) - timedelta(days=SEEN_KEEP_DAYS)).isoformat()
    seen = {k: v for k, v in seen.items() if v >= cutoff}
    with open(SEEN_FILE, "w") as f:
        json.dump(seen, f, indent=0, sort_keys=True)


def job_key(job):
    """Same job posted on two sites = same key."""
    norm = lambda s: re.sub(r"[^a-z0-9]", "", (s or "").lower())
    return f"{norm(job['title'])}|{norm(job['company'])}"


# ---------------------------------------------------------------------------
# Delivery
# ---------------------------------------------------------------------------

def detail_line(job):
    """'₹4–6 LPA · Posted 28 Sep · Closes 15 Oct'"""
    parts = [job.get("salary") or "Salary not listed"]
    parts.append(f"Posted {fmt_date(job.get('posted'))}" if job.get("posted") else "Posted date not listed")
    parts.append(f"Closes {fmt_date(job['closes'])}" if job.get("closes") else "No closing date listed")
    return " · ".join(parts)


def build_telegram_messages(fresher, unstated, today):
    lines = [f"<b>🐍 Python/Django developer jobs — {today}</b>",
             f"{len(fresher)} fresher-friendly · {len(unstated)} experience not stated\n"]

    def add(section, items):
        if not items:
            return
        lines.append(f"<b>{section}</b>")
        for j in items:
            lines.append(
                f"• <a href=\"{escape(j['url'])}\">{escape(j['title'])}</a>\n"
                f"   {escape(j['company'] or 'Unknown company')} · "
                f"{escape(j['location'] or 'Remote')} · {j['source']}\n"
                f"   💰 {escape(detail_line(j))}"
            )
        lines.append("")

    add("✅ Fresher-friendly", fresher)
    add("🔎 Experience not stated (check before applying)", unstated)

    messages, current = [], ""
    for line in lines:
        if len(current) + len(line) + 1 > 3900:
            messages.append(current)
            current = ""
        current += line + "\n"
    if current.strip():
        messages.append(current)
    return messages


def send_telegram(fresher, unstated, today):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not (token and chat_id):
        print("Telegram: skipped (not set up)")
        return
    for msg in build_telegram_messages(fresher, unstated, today):
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": msg, "parse_mode": "HTML",
                  "disable_web_page_preview": True},
            timeout=30,
        )
        if not r.ok:
            print(f"Telegram error: {r.text}")
    print("Telegram: sent")


def build_email_html(fresher, unstated, today):
    def rows(items):
        return "".join(
            f"<tr><td style='padding:8px;border-bottom:1px solid #eee'>"
            f"<a href='{escape(j['url'])}' style='font-weight:600;color:#1a56db'>{escape(j['title'])}</a><br>"
            f"<span style='color:#555'>{escape(j['company'] or 'Unknown company')} · "
            f"{escape(j['location'] or 'Remote')} · {j['source']}</span><br>"
            f"<span style='color:#0f6e56'>{escape(detail_line(j))}</span></td></tr>"
            for j in items
        )

    html = f"<h2 style='font-family:sans-serif'>Python/Django developer jobs — {today}</h2>"
    if fresher:
        html += ("<h3 style='font-family:sans-serif'>✅ Fresher-friendly</h3>"
                 f"<table style='font-family:sans-serif;width:100%'>{rows(fresher)}</table>")
    if unstated:
        html += ("<h3 style='font-family:sans-serif'>🔎 Experience not stated</h3>"
                 f"<table style='font-family:sans-serif;width:100%'>{rows(unstated)}</table>")
    return html


def send_email(fresher, unstated, today):
    user = os.getenv("GMAIL_ADDRESS")
    password = os.getenv("GMAIL_APP_PASSWORD")
    if not (user and password):
        print("Email: skipped (not set up)")
        return
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"{len(fresher) + len(unstated)} new Python/Django developer jobs — {today}"
    msg["From"] = user
    msg["To"] = os.getenv("EMAIL_TO") or user
    msg.attach(MIMEText(build_email_html(fresher, unstated, today), "html"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(user, password)
        s.send_message(msg)
    print("Email: sent")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def select_jobs(all_jobs, seen, now):
    fresher, unstated, keys = [], [], set()
    for job in all_jobs:
        if not job["url"] or not job["title"]:
            continue
        key = job_key(job)
        if key in seen or key in keys:
            continue
        if not location_ok(job) or not still_open(job, now):
            continue
        label = classify(job)
        if not label:
            continue
        keys.add(key)
        (fresher if label == "fresher" else unstated).append(job)

    newest_first = lambda j: j.get("posted") or datetime.min.replace(tzinfo=timezone.utc)
    fresher.sort(key=newest_first, reverse=True)
    unstated.sort(key=newest_first, reverse=True)
    return fresher, unstated, keys


def main():
    today = datetime.now(IST).strftime("%d %b %Y")
    print(f"Running for {today}")

    all_jobs = from_adzuna() + from_jooble() + from_remotive() + from_himalayas()

    seen = load_seen()
    now = datetime.now(timezone.utc)
    fresher, unstated, keys = select_jobs(all_jobs, seen, now)

    print(f"New matches: {len(fresher)} fresher, {len(unstated)} unstated")

    if not fresher and not unstated:
        print("Nothing new today.")
        return

    send_telegram(fresher, unstated, today)
    send_email(fresher, unstated, today)

    for k in keys:
        seen[k] = now.isoformat()
    save_seen(seen)


if __name__ == "__main__":
    sys.exit(main())
