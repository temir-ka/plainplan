"""Hand-written iCalendar (.ics, RFC 5545). No library: all-day events, optional monthly repeat."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

PRODID = "-//Plainplan//Family insurance//EN"


@dataclass
class CalEvent:
    uid: str
    day: date
    summary: str
    description: str = ""
    monthly_on_day: int | None = None  # repeat every month on this day (premiums)


def escape(text: str) -> str:
    """RFC 5545 TEXT escaping."""
    return (text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
            .replace("\r\n", "\\n").replace("\n", "\\n"))


def fold(line: str) -> str:
    """Lines longer than 75 octets continue on the next line after a single space."""
    out, current = [], ""
    for ch in line:
        if len((current + ch).encode()) > 75:
            out.append(current)
            current = " " + ch
        else:
            current += ch
    out.append(current)
    return "\r\n".join(out)


def calendar(events: list[CalEvent], name: str = "Plainplan") -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", f"PRODID:{PRODID}", "CALSCALE:GREGORIAN",
             f"X-WR-CALNAME:{escape(name)}"]
    for e in events:
        lines += ["BEGIN:VEVENT", f"UID:{e.uid}@plainplan", f"DTSTAMP:{stamp}",
                  f"DTSTART;VALUE=DATE:{e.day:%Y%m%d}", f"DTEND;VALUE=DATE:{e.day + timedelta(days=1):%Y%m%d}",
                  f"SUMMARY:{escape(e.summary)}"]
        if e.description:
            lines.append(f"DESCRIPTION:{escape(e.description)}")
        if e.monthly_on_day:
            # BYMONTHDAY=-1 means "last day of the month" for due days that some months don't have
            by_day = e.monthly_on_day if e.monthly_on_day <= 28 else -1
            lines.append(f"RRULE:FREQ=MONTHLY;BYMONTHDAY={by_day}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(fold(line) for line in lines) + "\r\n"
