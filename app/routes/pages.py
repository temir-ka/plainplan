"""Family pages: home, member, shared, /start, /family (edit members), settings + delete data."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, delete, func, select

from app import config
from app.db import get_session
from app.glass import stained_glass
from app.services import deadlines
from app.models import Chunk, Field, Household, Member, Policy, PolicyMember

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
templates.env.globals["ICONS"] = {"health": "🩺", "dental": "🦷", "auto": "🚗", "home": "🏠"}
templates.env.globals["TYPE_LABEL"] = {"health": "Health", "dental": "Dental", "auto": "Auto", "home": "Home"}
templates.env.globals["stained"] = stained_glass  # decorative stained-glass SVG background (design)

SessionDep = Annotated[Session, Depends(get_session)]
ROLES = ("parent", "child")
POLICY_TYPES = ("health", "dental", "auto", "home")
UPLOAD_ERRORS = {
    "type": "Pick a policy type.",
    "notpdf": "That file is not a PDF we can read.",
    "big": "That PDF is larger than 15 MB.",
    "scan": "This looks like a scan; please upload a text PDF.",
}


def render(request: Request, name: str, **context) -> HTMLResponse:
    return templates.TemplateResponse(request, name, {"household": request.state.household, **context})


def _members(session: Session, hh_id: str) -> list[Member]:
    return list(session.exec(select(Member).where(Member.household_id == hh_id).order_by(Member.id)))


def _policies(session: Session, hh_id: str) -> list[Policy]:
    return list(session.exec(select(Policy).where(Policy.household_id == hh_id).order_by(Policy.id)))


def covers(session: Session, hh_id: str) -> dict[int, set[int]]:
    """policy_id -> ids of members it covers. Missing or empty = Shared."""
    rows = session.exec(
        select(PolicyMember.policy_id, PolicyMember.member_id)
        .join(Policy, Policy.id == PolicyMember.policy_id)
        .where(Policy.household_id == hh_id)
    )
    result: dict[int, set[int]] = {}
    for policy_id, member_id in rows:
        result.setdefault(policy_id, set()).add(member_id)
    return result


def _verified_counts(session: Session, policies: list[Policy]) -> dict[int, int]:
    ids = [p.id for p in policies]
    if not ids:
        return {}
    rows = session.exec(
        select(Field.policy_id, func.count())
        .where(Field.policy_id.in_(ids), Field.verified == True)  # noqa: E712
        .group_by(Field.policy_id)
    )
    return dict(rows.all())


def _field_totals(session: Session, policies: list[Policy]) -> dict[int, int]:
    ids = [p.id for p in policies]
    if not ids:
        return {}
    rows = session.exec(select(Field.policy_id, func.count()).where(Field.policy_id.in_(ids)).group_by(Field.policy_id))
    return dict(rows.all())


def _own_member(session: Session, hh_id: str, member_id: int) -> Member:
    member = session.get(Member, member_id)
    if not member or member.household_id != hh_id:
        raise HTTPException(404)
    return member


@router.get("/", response_class=HTMLResponse)
def home(request: Request, session: SessionDep):
    hh = request.state.household
    policies = _policies(session, hh.id)
    cov = covers(session, hh.id)
    members = _members(session, hh.id)
    types_of = {m.id: [p.type for p in policies if m.id in cov.get(p.id, set())] for m in members}
    shared_types = [p.type for p in policies if not cov.get(p.id)]
    ava = next((m for m in members if m.nickname.lower() == "ava"), None)
    return render(request, "home.html", members=members, types_of=types_of, shared_types=shared_types,
                  example=_how_it_works_example(session, policies), ava=ava,
                  events=deadlines.group_premiums(deadlines.next_events(policies, owners=_owner_names(members, policies, cov))),
                  monthly=deadlines.monthly_total(policies))


def _owner_names(members: list[Member], policies: list[Policy], cov: dict[int, set[int]]) -> dict[int, str]:
    nick = {m.id: m.nickname for m in members}
    return {p.id: ", ".join(nick[i] for i in sorted(cov.get(p.id, set())) if i in nick) or "Shared" for p in policies}


def _how_it_works_example(session: Session, policies: list[Policy]) -> dict | None:
    """Real numbers for the "How it works" cards, taken from this family's own data (never made up)."""
    dental = [p for p in policies if p.type == "dental"]
    for p in dental + [p for p in policies if p.type != "dental"]:
        fields = list(session.exec(select(Field).where(Field.policy_id == p.id)))
        verified = [f for f in fields if f.verified]
        if not verified:
            continue
        shown = next((f for f in verified if f.name == "orthodontia"), verified[0])
        chunk = session.get(Chunk, shown.chunk_id)
        return {"policy": p, "total": len(fields), "verified": len(verified),
                "missing": len(fields) - len(verified), "quote": shown.quote, "page": chunk.page if chunk else "?"}
    return None


def _policies_page(request: Request, session: SessionDep, member: Member | None) -> HTMLResponse:
    hh = request.state.household
    cov = covers(session, hh.id)
    if member:
        policies = [p for p in _policies(session, hh.id) if member.id in cov.get(p.id, set())]
    else:
        policies = [p for p in _policies(session, hh.id) if not cov.get(p.id)]
    return render(
        request, "policies.html",
        title=member.nickname if member else "Shared",
        subtitle=member.role.capitalize() if member else "House, car, anything jointly owned",
        ask_label=f"Ask about {member.nickname}'s policies" if member else "Ask about shared policies",
        ask_scope=f"member:{member.id}" if member else "shared",
        member=member,
        policies=policies,
        verified=_verified_counts(session, policies),
        totals=_field_totals(session, policies),
        members=_members(session, hh.id),
        preselected=member.id if member else None,
        policy_types=POLICY_TYPES,
        error=UPLOAD_ERRORS.get(request.query_params.get("error", ""), ""),
    )


@router.get("/member/{member_id}", response_class=HTMLResponse)
def member_page(member_id: int, request: Request, session: SessionDep):
    return _policies_page(request, session, _own_member(session, request.state.household.id, member_id))


@router.get("/shared", response_class=HTMLResponse)
def shared_page(request: Request, session: SessionDep):
    return _policies_page(request, session, None)


@router.get("/start", response_class=HTMLResponse)
def start_form(request: Request):
    return render(request, "start.html")


@router.post("/start")
def start_family(session: SessionDep, name: Annotated[str, Form()] = ""):
    household = Household(id=str(uuid.uuid4()), name=name.strip()[:40] or "My family")
    session.add(household)
    session.commit()
    response = RedirectResponse("/family", status_code=303)
    response.set_cookie(config.COOKIE_NAME, household.id, max_age=config.COOKIE_MAX_AGE,
                        httponly=True, samesite="lax", secure=config.BASE_URL.startswith("https"))
    return response


def _members_context(session: Session, hh_id: str, error: str = "") -> dict:
    with_policies = set().union(*covers(session, hh_id).values())
    return {"members": _members(session, hh_id), "with_policies": with_policies, "roles": ROLES, "error": error}


def _members_partial(request: Request, session: Session, error: str = "") -> HTMLResponse:
    return render(request, "partials/members_list.html",
                  **_members_context(session, request.state.household.id, error))


@router.get("/family", response_class=HTMLResponse)
def family_page(request: Request, session: SessionDep):
    return render(request, "family.html", **_members_context(session, request.state.household.id))


@router.post("/members", response_class=HTMLResponse)
def add_member(
    request: Request,
    session: SessionDep,
    nickname: Annotated[str, Form()] = "",
    role: Annotated[str, Form()] = "",
):
    nickname = nickname.strip()[:30]
    if not nickname or role not in ROLES:
        return _members_partial(request, session, error="Add a nickname and pick a role.")
    session.add(Member(household_id=request.state.household.id, nickname=nickname, role=role))
    session.commit()
    return _members_partial(request, session)


@router.delete("/members/{member_id}", response_class=HTMLResponse)
def remove_member(member_id: int, request: Request, session: SessionDep):
    member = _own_member(session, request.state.household.id, member_id)
    has_policies = session.exec(select(PolicyMember).where(PolicyMember.member_id == member.id)).first()
    if has_policies:
        return _members_partial(request, session, error=f"Remove {member.nickname}'s policies first.")
    session.delete(member)
    session.commit()
    return _members_partial(request, session)


@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request):
    return render(request, "settings.html")


def delete_household(session: Session, hh_id: str) -> None:
    policy_ids = select(Policy.id).where(Policy.household_id == hh_id)
    session.execute(delete(Field).where(Field.policy_id.in_(policy_ids)))
    session.execute(delete(Chunk).where(Chunk.policy_id.in_(policy_ids)))
    session.execute(delete(PolicyMember).where(PolicyMember.policy_id.in_(policy_ids)))
    session.execute(delete(Policy).where(Policy.household_id == hh_id))
    session.execute(delete(Member).where(Member.household_id == hh_id))
    session.execute(delete(Household).where(Household.id == hh_id))
    session.commit()


@router.post("/delete-data")
def delete_data(request: Request, session: SessionDep):
    delete_household(session, request.state.household.id)
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie(config.COOKIE_NAME)
    return response
