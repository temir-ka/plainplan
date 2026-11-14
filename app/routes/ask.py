"""POST /ask (HTMX). Scope only filters which chunks BM25 may search:
household | member:{id} | shared | policy:{id}.

Flow: scope -> candidate policies -> BM25 top 6 -> LLM answer -> citations.verify -> answer or refusal.
"""

from dataclasses import dataclass
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select

from app.models import Chunk, Household, Member, Policy
from app.routes.pages import SessionDep, covers, render
from app.services import llm, search
from app.services.citations import Citation, verify

router = APIRouter()

MAX_QUESTION_CHARS = 300
STATUS_LABELS = {"covered": "Covered", "not_covered": "Not covered", "unclear": "Not clear from your documents"}


@dataclass
class ShownQuote:
    label: str  # "Delta Dental · dental"
    page: int
    text: str


def policy_label(p: Policy) -> str:
    return f"{p.insurer} · {p.type}" if p.insurer else p.type.capitalize()


def scoped_policies(session: Session, hh_id: str, scope: str, question: str) -> list[Policy]:
    policies = list(session.exec(select(Policy).where(Policy.household_id == hh_id).order_by(Policy.id)))
    cov = covers(session, hh_id)
    kind, _, raw_id = scope.partition(":")

    if kind == "policy":
        policies = [p for p in policies if str(p.id) == raw_id]
        if not policies:
            raise HTTPException(404)
        return policies
    if kind == "member":
        member = session.get(Member, int(raw_id)) if raw_id.isdigit() else None
        if member is None or member.household_id != hh_id:
            raise HTTPException(404)
        return [p for p in policies if member.id in cov.get(p.id, set())]
    if kind == "shared":
        return [p for p in policies if not cov.get(p.id)]

    # household: narrow by the person and policy type the question mentions, if any
    nicknames = {m.id: m.nickname for m in session.exec(select(Member).where(Member.household_id == hh_id))}
    people = search.mentioned_members(question, nicknames)
    types = search.narrow_policy_types(question)
    narrowed = [p for p in policies
                if (not people or people & cov.get(p.id, set()) or not cov.get(p.id))
                and (not types or p.type in types)]
    return narrowed or policies


def _refusal(request: Request, policy: Policy | None, message: str, question: str = "") -> HTMLResponse:
    return render(request, "partials/answer.html", status="unclear", label=STATUS_LABELS["unclear"],
                  answer="", quotes=[], refusal=message, policy=policy, question=question)


@router.post("/ask", response_class=HTMLResponse)
def ask(request: Request, session: SessionDep, q: Annotated[str, Form()] = "",
        scope: Annotated[str, Form()] = "household"):
    hh: Household = request.state.household
    question = q.strip()[:MAX_QUESTION_CHARS]
    if not question:
        return HTMLResponse("")

    policies = scoped_policies(session, hh.id, scope, question)
    if not policies:
        return _refusal(request, None, "There are no policies here yet. Add one with + Add policy.", question)

    by_policy = {p.id: p for p in policies}
    chunks = list(session.exec(select(Chunk).where(Chunk.policy_id.in_(by_policy))))
    found = search.search(chunks, question)
    if not found:  # name an insurer only if the question clearly points to one kind of policy
        only_one_kind = len({p.type for p in policies}) == 1
        return _refusal(request, policies[0] if only_one_kind else None,
                        "I couldn't find this in your documents.", question)
    top_policy = by_policy[found[0].policy_id]

    notes = _policy_notes(session, hh.id, by_policy)
    texts = {c.id: c.text for c in found}
    result = llm.answer_question(question, found, notes)
    _count_question(session, hh.id)
    if result is None:
        return _refusal(request, top_policy, "I couldn't check your documents right now.", question)

    if result.status == "off_topic":
        return _refusal(request, None, "I can only answer questions about your family's policies.", question)

    check = _verify(result, texts)
    if result.status in ("covered", "not_covered") and not check.ok:  # one retry, telling the LLM exactly what failed
        retry = llm.answer_question(question, found, notes, feedback=_why_rejected(result, check))
        if retry is not None and retry.status != "off_topic":
            result, check = retry, _verify(retry, texts)

    chunk_by_id = {c.id: c for c in found}
    if result.status == "unclear" or not check.ok:
        return _refusal(request, top_policy, "I couldn't find this in your documents.", question)

    quotes = [ShownQuote(policy_label(by_policy[chunk_by_id[c.chunk_id].policy_id]),
                         chunk_by_id[c.chunk_id].page, c.quote) for c in check.verified]
    return render(request, "partials/answer.html", status=result.status, label=STATUS_LABELS[result.status],
                  answer=result.answer, quotes=quotes, refusal="", policy=top_policy, question=question)


def _verify(result: llm.Answer, texts: dict[int, str]):
    return verify(result.answer, [Citation(c.chunk_id, c.quote) for c in result.citations], texts)


def _why_rejected(result: llm.Answer, check) -> str:
    bad = len(result.citations) - len(check.verified)
    parts = [f"{bad} quote(s) were not found word for word in their chunk"] if bad else []
    if check.missing_numbers:
        parts.append("these numbers are not in any verified quote: " + ", ".join(check.missing_numbers))
    return "; ".join(parts or ["no verified quote"]) + ". Answer again: drop those numbers or quote the exact text that has them."


def _policy_notes(session: Session, hh_id: str, by_policy: dict[int, Policy]) -> dict[int, str]:
    """Tell the LLM whom each policy covers, so "Dad's deductible" finds Dad's plan."""
    names = {m.id: m.nickname for m in session.exec(select(Member).where(Member.household_id == hh_id))}
    cov = covers(session, hh_id)
    notes = {}
    for pid, p in by_policy.items():
        who = ", ".join(names[m] for m in sorted(cov.get(pid, ())) if m in names)
        notes[pid] = f"{p.type} plan; covers {who}" if who else f"{p.type} policy; shared by the household"
    return notes


def _count_question(session: Session, hh_id: str) -> None:
    household = session.get(Household, hh_id)
    household.questions_used += 1
    session.add(household)
    session.commit()
