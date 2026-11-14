"""Add a policy (PDF upload) and the policy page.

The uploaded file lives only in a temp file while we extract text, then it is deleted.
"""

import os
import tempfile
from datetime import date
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select

from app.models import Chunk, Field, Member, Policy, PolicyMember
from app.routes.pages import POLICY_TYPES, SessionDep, covers, render
from app.services.ingest import read_and_extract, save_document
from app.services.pdf import ScannedPdfError

router = APIRouter()

MAX_UPLOAD_BYTES = 15 * 1024 * 1024


def _save_to_temp(upload: UploadFile) -> Path:
    fd, name = tempfile.mkstemp(suffix=".pdf")
    size = 0
    with os.fdopen(fd, "wb") as out:
        while block := upload.file.read(1024 * 1024):
            size += len(block)
            if size > MAX_UPLOAD_BYTES:
                out.close()
                os.unlink(name)
                raise ValueError("big")
            out.write(block)
    return Path(name)


def _back_url(member_ids: list[int], error: str) -> str:
    page = f"/member/{member_ids[0]}" if len(member_ids) == 1 else "/shared" if not member_ids else "/"
    return f"{page}?error={error}"


@router.post("/policies")
def add_policy(
    request: Request,
    session: SessionDep,
    file: UploadFile,
    type: Annotated[str, Form()] = "",
    member_ids: Annotated[list[int], Form()] = [],
):
    hh_id = request.state.household.id
    own_ids = {m.id for m in session.exec(select(Member).where(Member.household_id == hh_id))}
    member_ids = [m for m in member_ids if m in own_ids]  # ignore ids from other families
    if type not in POLICY_TYPES:
        return RedirectResponse(_back_url(member_ids, "type"), status_code=303)

    try:
        path = _save_to_temp(file)
    except ValueError:
        return RedirectResponse(_back_url(member_ids, "big"), status_code=303)
    try:
        if path.read_bytes()[:5] != b"%PDF-":
            return RedirectResponse(_back_url(member_ids, "notpdf"), status_code=303)
        chunks, extraction = read_and_extract(session, path, type)
    except ScannedPdfError:
        return RedirectResponse(_back_url(member_ids, "scan"), status_code=303)
    except Exception:  # broken or encrypted PDF
        return RedirectResponse(_back_url(member_ids, "notpdf"), status_code=303)
    finally:
        path.unlink(missing_ok=True)  # never keep the original file

    policy = Policy(household_id=hh_id, type=type)
    session.add(policy)
    session.flush()
    session.add_all(PolicyMember(policy_id=policy.id, member_id=m) for m in member_ids)
    save_document(session, policy, chunks, extraction)
    return RedirectResponse(f"/policy/{policy.id}", status_code=303)


def own_policy(session: Session, hh_id: str, policy_id: int) -> Policy:
    policy = session.get(Policy, policy_id)
    if not policy or policy.household_id != hh_id:
        raise HTTPException(404)
    return policy


@router.get("/policy/{policy_id}", response_class=HTMLResponse)
def policy_page(policy_id: int, request: Request, session: SessionDep):
    return _render_policy(policy_id, request, session)


def _render_policy(policy_id: int, request: Request, session: Session, details_error: str = "") -> HTMLResponse:
    hh_id = request.state.household.id
    policy = own_policy(session, hh_id, policy_id)
    member_ids = covers(session, hh_id).get(policy.id, set())
    covered_members = list(session.exec(select(Member).where(Member.id.in_(member_ids)).order_by(Member.id)))
    names = [m.nickname for m in covered_members]
    if not covered_members:
        back_url, back_label = "/shared", "Shared"
    elif len(covered_members) == 1:
        back_url, back_label = f"/member/{covered_members[0].id}", covered_members[0].nickname
    else:
        back_url, back_label = "/", "Family"
    chunks = list(session.exec(select(Chunk).where(Chunk.policy_id == policy.id)))
    fields = list(session.exec(select(Field).where(Field.policy_id == policy.id).order_by(Field.id)))
    return render(
        request, "policy.html",
        policy=policy,
        covered=", ".join(names) or "Shared",
        pages=max((c.page for c in chunks), default=0),
        chunk_pages={c.id: c.page for c in chunks},
        fields=fields,
        ask_label="Ask about this policy",
        ask_scope=f"policy:{policy.id}",
        details_error=details_error,
        back_url=back_url,
        back_label=back_label,
    )


def _own_field(session: Session, hh_id: str, field_id: int) -> Field:
    field = session.get(Field, field_id)
    if not field:
        raise HTTPException(404)
    own_policy(session, hh_id, field.policy_id)  # 404 if it belongs to another family
    return field


def _field_partial(request: Request, session: Session, field: Field) -> HTMLResponse:
    chunk = session.get(Chunk, field.chunk_id) if field.chunk_id else None
    return render(request, "partials/field.html", f=field, page=chunk.page if chunk else None,
                  policy=session.get(Policy, field.policy_id))


@router.get("/fields/{field_id}", response_class=HTMLResponse)
def show_field(field_id: int, request: Request, session: SessionDep):
    return _field_partial(request, session, _own_field(session, request.state.household.id, field_id))


@router.get("/fields/{field_id}/edit", response_class=HTMLResponse)
def edit_field_form(field_id: int, request: Request, session: SessionDep):
    return render(request, "partials/field_edit.html", f=_own_field(session, request.state.household.id, field_id))


@router.post("/fields/{field_id}", response_class=HTMLResponse)
def save_field(field_id: int, request: Request, session: SessionDep, value: Annotated[str, Form()] = ""):
    """A typed value is the user's, not the document's: no quote, not verified."""
    field = _own_field(session, request.state.household.id, field_id)
    field.value, field.source, field.verified, field.quote, field.chunk_id = value.strip()[:120], "user", False, "", None
    session.add(field)
    session.commit()
    return _field_partial(request, session, field)


class DetailsError(ValueError):
    """A message we can show the user as is."""


def _parse_details(form: dict) -> dict:
    """Raises DetailsError (our message) or ValueError (unparseable date/number)."""
    out: dict = {"insurer": form["insurer"].strip()[:60], "claims_phone": form["claims_phone"].strip()[:30]}
    for key in ("period_start", "period_end"):
        out[key] = date.fromisoformat(form[key]) if form[key] else None
    if out["period_start"] and out["period_end"] and out["period_end"] < out["period_start"]:
        raise DetailsError("The end date is before the start date.")
    out["premium_monthly"] = float(form["premium_monthly"]) if form["premium_monthly"] else None
    if out["premium_monthly"] is not None and not 0 <= out["premium_monthly"] <= 100_000:
        raise DetailsError("The premium looks wrong.")
    out["premium_due_day"] = int(form["premium_due_day"]) if form["premium_due_day"] else None
    if out["premium_due_day"] is not None and not 1 <= out["premium_due_day"] <= 31:
        raise DetailsError("The due day must be between 1 and 31.")
    return out


@router.post("/policy/{policy_id}/details")
def save_details(
    policy_id: int, request: Request, session: SessionDep,
    insurer: Annotated[str, Form()] = "", claims_phone: Annotated[str, Form()] = "",
    period_start: Annotated[str, Form()] = "", period_end: Annotated[str, Form()] = "",
    premium_monthly: Annotated[str, Form()] = "", premium_due_day: Annotated[str, Form()] = "",
):
    policy = own_policy(session, request.state.household.id, policy_id)
    form = {"insurer": insurer, "claims_phone": claims_phone, "period_start": period_start,
            "period_end": period_end, "premium_monthly": premium_monthly, "premium_due_day": premium_due_day}
    try:
        details = _parse_details(form)
    except DetailsError as e:
        return _render_policy(policy_id, request, session, details_error=str(e))
    except ValueError:
        return _render_policy(policy_id, request, session, details_error="Check the dates and numbers.")
    for key, value in details.items():
        setattr(policy, key, value)
    policy.details_edited = True
    session.add(policy)
    session.commit()
    return RedirectResponse(f"/policy/{policy.id}", status_code=303)
