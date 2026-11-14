"""Family pages: home, member, shared, /start, /family (edit members), settings + delete data."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, delete, func, select

from app import config
from app.db import get_session
from app.models import Chunk, Field, Household, Member, Policy

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
templates.env.globals["ICONS"] = {"health": "🩺", "dental": "🦷", "auto": "🚗", "home": "🏠"}

SessionDep = Annotated[Session, Depends(get_session)]
ROLES = ("parent", "child")


def render(request: Request, name: str, **context) -> HTMLResponse:
    return templates.TemplateResponse(request, name, {"household": request.state.household, **context})


def _members(session: Session, hh_id: str) -> list[Member]:
    return list(session.exec(select(Member).where(Member.household_id == hh_id).order_by(Member.id)))


def _policies(session: Session, hh_id: str) -> list[Policy]:
    return list(session.exec(select(Policy).where(Policy.household_id == hh_id).order_by(Policy.id)))


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


def _own_member(session: Session, hh_id: str, member_id: int) -> Member:
    member = session.get(Member, member_id)
    if not member or member.household_id != hh_id:
        raise HTTPException(404)
    return member


@router.get("/", response_class=HTMLResponse)
def home(request: Request, session: SessionDep):
    hh = request.state.household
    policies = _policies(session, hh.id)
    tiles = [
        {"title": m.nickname, "subtitle": m.role.capitalize(), "href": f"/member/{m.id}",
         "types": [p.type for p in policies if p.member_id == m.id]}
        for m in _members(session, hh.id)
    ]
    tiles.append({"title": "Shared", "subtitle": "House, car, anything joint", "href": "/shared",
                  "types": [p.type for p in policies if p.member_id is None]})
    return render(request, "home.html", tiles=tiles, has_members=len(tiles) > 1)


def _policies_page(request: Request, session: SessionDep, member: Member | None) -> HTMLResponse:
    hh = request.state.household
    member_id = member.id if member else None
    policies = [p for p in _policies(session, hh.id) if p.member_id == member_id]
    return render(
        request, "policies.html",
        title=member.nickname if member else "Shared",
        subtitle=member.role.capitalize() if member else "House, car, anything jointly owned",
        ask_label=f"Ask about {member.nickname}'s policies" if member else "Ask about shared policies",
        ask_scope=f"member:{member.id}" if member else "shared",
        policies=policies,
        verified=_verified_counts(session, policies),
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


def _members_partial(request: Request, session: Session, error: str = "") -> HTMLResponse:
    hh = request.state.household
    with_policies = {p.member_id for p in _policies(session, hh.id)}
    return render(request, "partials/members_list.html", members=_members(session, hh.id),
                  with_policies=with_policies, roles=ROLES, error=error)


@router.get("/family", response_class=HTMLResponse)
def family_page(request: Request, session: SessionDep):
    hh = request.state.household
    with_policies = {p.member_id for p in _policies(session, hh.id)}
    return render(request, "family.html", members=_members(session, hh.id),
                  with_policies=with_policies, roles=ROLES, error="")


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
    has_policies = session.exec(select(Policy).where(Policy.member_id == member.id)).first()
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
