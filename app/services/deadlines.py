"""Deadlines engine. Pure Python, no LLM.

- next_events(): the "Next 90 days" feed from policy dates the user (or demo JSON) entered.
- find_deadline(): a deadline inside a verified policy quote ("within 60 days").
"""

import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Protocol

WINDOW_DAYS = 90
SOON_DAYS = 14

_WITHIN = re.compile(r"\bwithin\s+(\d{1,3})\s+(day|days|hour|hours)\b", re.IGNORECASE)
TYPE_LABEL = {"health": "Health", "dental": "Dental", "auto": "Auto", "home": "Home"}


class PolicyLike(Protocol):
    id: int | None
    type: str
    insurer: str
    period_start: date | None
    period_end: date | None
    premium_monthly: float | None
    premium_due_day: int | None


@dataclass
class Event:
    when: date
    kind: str  # "renewal" | "premium" | "reset"
    title: str
    sub: str
    amount: float | None
    policy_id: int | None

    @property
    def status(self) -> str:
        return "soon" if (self.when - date.today()).days <= SOON_DAYS else "ok"


def find_deadline(quote: str) -> str:
    """'...send us, within 60 days after our request, your proof of loss' -> 'within 60 days'. '' if none."""
    m = _WITHIN.search(quote)
    return f"within {m.group(1)} {m.group(2).lower()}" if m else ""


def deadline_days(quote: str) -> int | None:
    m = _WITHIN.search(quote)
    if not m:
        return None
    n = int(m.group(1))
    return max(1, n // 24) if m.group(2).lower().startswith("hour") else n


def _day_in_month(year: int, month: int, day: int) -> date:
    """Due day 31 in February -> Feb 28/29 (the bill is still due that month)."""
    for d in (day, 30, 29, 28):
        try:
            return date(year, month, d)
        except ValueError:
            continue
    raise ValueError(day)


def next_due(due_day: int, today: date) -> date:
    this_month = _day_in_month(today.year, today.month, due_day)
    if this_month >= today:
        return this_month
    year, month = (today.year + 1, 1) if today.month == 12 else (today.year, today.month + 1)
    return _day_in_month(year, month, due_day)


def next_anniversary(start: date, today: date) -> date:
    for year in (today.year, today.year + 1):
        candidate = _day_in_month(year, start.month, start.day)
        if candidate >= today:
            return candidate
    raise AssertionError("unreachable")


def _name(p: PolicyLike) -> str:
    return p.insurer or f"{TYPE_LABEL.get(p.type, p.type)} policy"


def next_events(policies: list[PolicyLike], today: date | None = None, days: int = WINDOW_DAYS,
                owners: dict[int, str] | None = None) -> list[Event]:
    """owners: policy_id -> "Leo, Ava" / "Shared", so two plans from the same insurer stay distinguishable."""
    today = today or date.today()
    end = today + timedelta(days=days)
    owners = owners or {}
    events: list[Event] = []
    for p in policies:
        label = TYPE_LABEL.get(p.type, p.type)
        who = f" · {owners[p.id]}" if p.id in owners else ""
        if p.period_end and today <= p.period_end <= end:
            events.append(Event(p.period_end, "renewal", f"{label} policy ends", f"{_name(p)}{who}", None, p.id))
        if p.premium_monthly and p.premium_due_day:
            due = next_due(p.premium_due_day, today)
            if due <= end:
                events.append(Event(due, "premium", f"{label} premium due", _name(p), p.premium_monthly, p.id))
        if p.type == "dental" and p.period_start:
            reset = next_anniversary(p.period_start, today)
            if reset <= end and reset != p.period_start:
                events.append(Event(reset, "reset", "Dental annual maximum resets", f"{_name(p)}{who}", None, p.id))
    return sorted(events, key=lambda e: (e.when, e.kind, e.title))


def group_premiums(events: list[Event]) -> list[Event]:
    """Several premiums on the same day -> one line "Premiums due: Health, Dental" with the sum."""
    out: list[Event] = []
    by_day: dict[date, list[Event]] = {}
    for e in events:
        if e.kind == "premium":
            by_day.setdefault(e.when, []).append(e)
        else:
            out.append(e)
    for day, group in by_day.items():
        if len(group) == 1:
            out.append(group[0])
        else:
            kinds = ", ".join(g.title.removesuffix(" premium due") for g in group)
            out.append(Event(day, "premium", f"Premiums due: {kinds}", f"{len(group)} policies",
                             sum(g.amount or 0 for g in group), None))
    return sorted(out, key=lambda e: (e.when, e.kind, e.title))


def monthly_total(policies: list[PolicyLike]) -> float:
    return round(sum(p.premium_monthly or 0 for p in policies), 2)
