"""Calendar downloads (.ics): everything for the family, or one deadline from a situation step."""

from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from sqlmodel import select

from app.models import Policy
from app.routes.pages import SessionDep
from app.services import deadlines, ics

router = APIRouter()
ICS_TYPE = "text/calendar; charset=utf-8"


def _download(body: str, filename: str) -> Response:
    return Response(body, media_type=ICS_TYPE, headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/calendar.ics")
def family_calendar(request: Request, session: SessionDep):
    """Renewals in the next year + premiums as monthly repeating events."""
    hh = request.state.household
    policies = list(session.exec(select(Policy).where(Policy.household_id == hh.id)))
    events = [ics.CalEvent(f"{e.kind}-{e.policy_id}-{e.when:%Y%m%d}", e.when, e.title, e.sub)
              for e in deadlines.next_events(policies, days=365) if e.kind != "premium"]
    for p in policies:
        if p.premium_monthly and p.premium_due_day:
            first = deadlines.next_due(p.premium_due_day, date.today())
            label = deadlines.TYPE_LABEL.get(p.type, p.type)
            events.append(ics.CalEvent(f"premium-{p.id}", first, f"{label} premium due: ${p.premium_monthly:,.0f}",
                                       p.insurer, monthly_on_day=p.premium_due_day))
    return _download(ics.calendar(events, f"{hh.name} insurance"), "plainplan.ics")


@router.get("/calendar/deadline.ics")
def deadline_calendar(request: Request, session: SessionDep, policy_id: int, days: int, what: str = "Policy deadline"):
    """One event `days` from today, e.g. "within 60 days" from a verified quote in a situation step."""
    policy = session.get(Policy, policy_id)
    if not policy or policy.household_id != request.state.household.id or not 1 <= days <= 365:
        raise HTTPException(404)
    day = date.today() + timedelta(days=days)
    summary = f"{deadlines.TYPE_LABEL.get(policy.type, policy.type)}: {what[:80]}"
    description = f"Your policy says: within {days} days. Check the exact start of the clock in the policy."
    return _download(ics.calendar([ics.CalEvent(f"deadline-{policy.id}-{day:%Y%m%d}", day, summary, description)]),
                     "plainplan-deadline.ics")
