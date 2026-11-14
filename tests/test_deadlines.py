from dataclasses import dataclass
from datetime import date

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.db import engine
from app.main import app
from app.models import Policy
from app.services import ics
from app.services.deadlines import (
    deadline_days, find_deadline, group_premiums, monthly_total, next_due, next_events,
)

TODAY = date(2026, 11, 14)


@dataclass
class P:
    id: int
    type: str
    insurer: str = ""
    period_start: date | None = None
    period_end: date | None = None
    premium_monthly: float | None = None
    premium_due_day: int | None = None


def test_next_due_handles_short_months_and_year_end():
    assert next_due(15, TODAY) == date(2026, 11, 15)
    assert next_due(1, TODAY) == date(2026, 12, 1)
    assert next_due(31, date(2027, 2, 10)) == date(2027, 2, 28)
    assert next_due(5, date(2026, 12, 20)) == date(2027, 1, 5)


def test_next_90_days_feed():
    policies = [
        P(1, "auto", "Heartland", date(2026, 7, 15), date(2027, 1, 15), 222, 15),
        P(2, "home", "", date(2026, 3, 1), date(2027, 3, 1), 145, 1),     # ends after the window
        P(3, "dental", "Delta", date(2026, 1, 1), date(2026, 12, 31), 38, 1),
        P(4, "health"),                                                  # nothing entered
    ]
    events = next_events(policies, TODAY)
    got = [(e.when, e.kind, e.policy_id) for e in events]
    assert (date(2027, 1, 15), "renewal", 1) in got
    assert (date(2026, 11, 15), "premium", 1) in got
    assert (date(2026, 12, 1), "premium", 2) in got
    assert (date(2026, 12, 31), "renewal", 3) in got
    assert (date(2027, 1, 1), "reset", 3) in got  # dental max resets on the plan-year anniversary
    assert not any(e.policy_id == 2 and e.kind == "renewal" for e in events)
    assert not any(e.policy_id == 4 for e in events)
    assert [e.when for e in events] == sorted(e.when for e in events)
    assert monthly_total(policies) == 405


def test_premiums_on_one_day_are_grouped_and_owners_shown():
    policies = [P(1, "health", "Sample", None, None, 410, 1), P(2, "home", "Sample Home", None, None, 145, 1),
                P(3, "dental", "Delta", date(2026, 1, 1), date(2026, 12, 31), 38, 15)]
    events = group_premiums(next_events(policies, TODAY, owners={3: "Leo, Ava"}))
    dec1 = [e for e in events if e.when == date(2026, 12, 1)]
    assert len(dec1) == 1 and dec1[0].title == "Premiums due: Health, Home" and dec1[0].amount == 555
    assert any(e.kind == "renewal" and e.sub == "Delta · Leo, Ava" for e in events)


def test_deadline_in_quote():
    assert find_deadline("within 60 days after our request") == "within 60 days"
    assert deadline_days("within 60 days after our request") == 60
    assert deadline_days("within 72 hours") == 3
    assert deadline_days("promptly") is None


def test_ics_escaping_folding_and_repeat():
    body = ics.calendar([
        ics.CalEvent("a", date(2027, 1, 15), "Auto policy ends; renew, or replace", "x" * 200),
        ics.CalEvent("b", date(2026, 12, 31), "Premium due", monthly_on_day=31),
    ])
    assert body.startswith("BEGIN:VCALENDAR\r\n") and body.endswith("END:VCALENDAR\r\n")
    assert "SUMMARY:Auto policy ends\\; renew\\, or replace" in body
    assert "DTSTART;VALUE=DATE:20270115" in body and "DTEND;VALUE=DATE:20270116" in body
    assert "RRULE:FREQ=MONTHLY;BYMONTHDAY=-1" in body  # day 31 -> last day of every month
    assert all(len(line.encode()) <= 75 for line in body.split("\r\n"))


def test_calendar_downloads():
    with TestClient(app) as client:
        client.get("/")
        hh = client.cookies["hh_id"]
        with Session(engine) as s:
            p = Policy(household_id=hh, type="auto", insurer="Heartland", period_end=date(2027, 1, 15),
                       premium_monthly=222, premium_due_day=15)
            s.add(p)
            s.commit()
            pid = p.id
        r = client.get("/calendar.ics")
        assert r.headers["content-type"].startswith("text/calendar")
        assert "Auto policy ends" in r.text and "RRULE:FREQ=MONTHLY;BYMONTHDAY=15" in r.text
        r = client.get(f"/calendar/deadline.ics?policy_id={pid}&days=60&what=Send proof of loss")
        assert r.status_code == 200 and "Send proof of loss" in r.text
        with TestClient(app) as other:
            other.get("/")
            assert other.get(f"/calendar/deadline.ics?policy_id={pid}&days=60").status_code == 404
        assert client.get(f"/calendar/deadline.ics?policy_id={pid}&days=9999").status_code == 404
        assert "Next 90 days" in client.get("/").text
