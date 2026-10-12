from datetime import date

import pytest

from jobhunt_mcp import db, tracker
from jobhunt_mcp.dates import parse_when
from jobhunt_mcp.mail import DemoMail

MON = date(2026, 10, 12)  # a Monday


@pytest.fixture
def conn():
    with db.connect(":memory:") as c:
        yield c


def seeded(conn):
    for company, role in [("Zoho", "Python Developer"), ("Freshworks", "SDE"),
                          ("Razorpay", "Backend Engineer"), ("Swiggy", "SDE")]:
        tracker.add_application(conn, company, role)


def test_parse_when():
    assert parse_when("tomorrow", MON) == date(2026, 10, 13)
    assert parse_when("Friday", MON) == date(2026, 10, 16)
    assert parse_when("monday", MON) == date(2026, 10, 19)  # never "today" for a bare weekday
    assert parse_when("in 2 weeks", MON) == date(2026, 10, 26)
    assert parse_when("2026-11-01", MON) == date(2026, 11, 1)
    assert parse_when("30 October", MON) == date(2026, 10, 30)
    with pytest.raises(ValueError):
        parse_when("whenever", MON)


def test_add_and_list(conn):
    seeded(conn)
    assert "already" in tracker.add_application(conn, "Zoho", "Python Developer")
    assert tracker.list_applications(conn).startswith("You have 4 applications: 4 applied")
    assert "no interview" in tracker.list_applications(conn, "interview")
    assert "don't know" in tracker.list_applications(conn, "bogus")


def test_followups(conn):
    seeded(conn)
    assert "tomorrow" in tracker.add_followup(conn, "zoho", "tomorrow", today=MON)
    assert "Friday" in tracker.add_followup(conn, "Zoho", "Friday", "send thank-you", today=MON)
    assert "couldn't find" in tracker.add_followup(conn, "Acme", "Friday", today=MON)
    assert "couldn't understand" in tracker.add_followup(conn, "Zoho", "someday", today=MON)
    assert "Nothing due today" in tracker.todays_followups(conn, MON)
    out = tracker.todays_followups(conn, date(2026, 10, 16))
    assert "2 follow-ups" in out and "Zoho" in out and "send thank-you" in out
    assert "done" in tracker.complete_followup(conn, "Zoho")
    assert "no follow-ups" in tracker.todays_followups(conn, date(2026, 10, 16))


def test_check_new_replies_updates_status_and_announces_once(conn):
    seeded(conn)
    out = tracker.check_new_replies(conn, DemoMail())
    assert "3 new replies" in out
    assert "Zoho wants to set up an interview" in out
    assert "Freshworks said they're not moving forward" in out
    assert "Razorpay sent an assessment" in out
    assert "Swiggy" not in out  # job-board noise ignored
    assert "1 interview" in tracker.list_applications(conn)
    assert tracker.check_new_replies(conn, DemoMail()) == "No new replies from companies."


def test_reply_never_downgrades_final_status(conn):
    seeded(conn)
    tracker.update_status(conn, "Freshworks", "offer")
    tracker.check_new_replies(conn, DemoMail())
    row = db.find_application(conn, "Freshworks")
    assert row["status"] == "offer"


def test_no_applications(conn):
    assert "aren't tracking" in tracker.check_new_replies(conn, DemoMail())
