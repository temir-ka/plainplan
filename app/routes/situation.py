"""Something happened? (/situation). Separate from Ask.

text -> 911 banner (regex OR LLM flag) -> LLM picks a situation type from a fixed enum
     -> routing.py (plain dict) picks the family's policies -> "Who was hurt?" if needed
     -> per policy: BM25 with template queries -> LLM steps -> keep only steps whose quote verifies
     -> general checklist (templates, not from the policy) + claims phone.
"""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Annotated

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select

from app.models import Chunk, Household, Member, Policy
from app.routes.ask import policy_label
from app.routes.pages import SessionDep, covers, render
from app.services import llm, redflags, routing, search
from app.services.citations import numbers_in, quote_in_chunk
from app.services.deadlines import deadline_days, find_deadline

router = APIRouter()

MAX_TEXT_CHARS = 500

# What to look for in each policy type, whatever the wording of the user's text.
STEP_QUERIES = {
    "auto": "duties after an accident or loss notify us promptly how when where police injured witnesses",
    "home": "duties after loss give prompt notice protect property proof of loss within days inventory",
    "health": "emergency room urgent care hospital stay preauthorization claim notice network",
    "dental": "emergency dental pain claim pre-treatment estimate deductible",
}

SITUATION_TITLES = {
    "car_accident": "Car accident", "water_damage": "Water damage", "fire": "Fire", "theft": "Theft",
    "storm_damage": "Storm damage", "dental_problem": "Dental problem", "illness": "Illness",
    "injury": "Injury", "other": "Something else",
}


@dataclass
class ShownStep:
    text: str
    page: int
    quote: str
    deadline: str
    deadline_days: int | None = None


@dataclass
class PolicyPlan:
    policy: Policy
    label: str
    steps: list[ShownStep] = field(default_factory=list)


@router.get("/situation", response_class=HTMLResponse)
def situation_page(request: Request, text: str = ""):
    return render(request, "situation.html", prefill=text[:500])


MIN_STEP_QUOTE_CHARS = 25  # a fragment like "Does this plan use a" exists in the text but proves no step


def verified_steps(result: llm.Steps | None, chunks: list[Chunk]) -> list[ShownStep]:
    by_id = {c.id: c for c in chunks}
    shown = []
    for s in result.steps if result else []:
        chunk = by_id.get(s.chunk_id)
        if (chunk and len(s.quote.strip()) >= MIN_STEP_QUOTE_CHARS and quote_in_chunk(s.quote, chunk.text)
                and numbers_in(s.text) <= numbers_in(s.quote)):
            shown.append(ShownStep(s.text, chunk.page, s.quote, find_deadline(s.quote), deadline_days(s.quote)))
    return shown[:4]


def _plan_for(text: str, policy: Policy, chunks: list[Chunk]) -> PolicyPlan:
    found = search.search(chunks, f"{STEP_QUERIES.get(policy.type, '')} {text}")
    steps = verified_steps(llm.situation_steps(text, policy.type, found), found) if found else []
    return PolicyPlan(policy, policy_label(policy), steps)


def _who_was_hurt(session: Session, hh_id: str) -> list[Member]:
    return list(session.exec(select(Member).where(Member.household_id == hh_id).order_by(Member.id)))


@router.post("/situation", response_class=HTMLResponse)
def situation(request: Request, session: SessionDep, text: Annotated[str, Form()] = "",
              member_id: Annotated[str, Form()] = ""):
    hh: Household = request.state.household
    text = text.strip()[:MAX_TEXT_CHARS]
    if not text:
        return HTMLResponse("")

    members = _who_was_hurt(session, hh.id)
    nicknames = {m.id: m.nickname for m in members}
    guess = llm.classify_situation(text, list(nicknames.values()))
    situation_type = guess.situation if guess else "other"
    banner = redflags.show_911_banner(text, llm_emergency=bool(guess and guess.emergency))
    someone_hurt = redflags.mentions_injury(text) or bool(guess and guess.someone_hurt)

    # who: the button they pressed > a nickname in the text > the LLM's guess (only if it is a real member)
    chosen = int(member_id) if member_id.isdigit() and int(member_id) in nicknames else None
    named = search.mentioned_members(text, nicknames)
    by_llm = [mid for mid, nick in nicknames.items() if guess and guess.affected.lower() == nick.lower()]
    who = chosen or (min(named) if len(named) == 1 else None) or (by_llm[0] if by_llm else None)

    policies = list(session.exec(select(Policy).where(Policy.household_id == hh.id).order_by(Policy.id)))
    routed = routing.route(situation_type, policies, covers(session, hh.id), someone_hurt=someone_hurt, member_id=who,
                           text=text)

    context = {"text": text, "banner": banner, "title": SITUATION_TITLES[situation_type],
               "checklist": routing.CHECKLISTS[situation_type], "who": nicknames.get(who, "")}
    if routed.needs_person:
        return render(request, "partials/situation_result.html", ask_who=members, plans=[], **context)

    chunks_by_policy: dict[int, list[Chunk]] = {p.id: [] for p in routed.policies}
    for c in session.exec(select(Chunk).where(Chunk.policy_id.in_(chunks_by_policy))):
        chunks_by_policy[c.policy_id].append(c)
    with ThreadPoolExecutor(max_workers=4) as pool:  # one LLM call per policy, in parallel (no DB access inside)
        plans = list(pool.map(lambda p: _plan_for(text, p, chunks_by_policy[p.id]), routed.policies))
    _count(session, hh.id)  # after the threads: commit expires loaded objects
    return render(request, "partials/situation_result.html", ask_who=[], plans=plans, **context)


def _count(session: Session, hh_id: str) -> None:
    household = session.get(Household, hh_id)
    household.questions_used += 1  # situations and questions share the free limit
    session.add(household)
    session.commit()
