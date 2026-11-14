"""Add a policy (PDF upload) and the policy page.

The uploaded file lives only in a temp file while we extract text, then it is deleted.
"""

import os
import tempfile
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select

from app.models import Chunk, Field, Member, Policy, PolicyMember
from app.routes.pages import POLICY_TYPES, SessionDep, covers, render
from app.services import llm
from app.services.citations import appears_in, verify_field
from app.services.pdf import ScannedPdfError, read_policy_pdf

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
        chunks = read_policy_pdf(path)
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
    rows = [Chunk(policy_id=policy.id, page=c.page, section=c.section, text=c.text) for c in chunks]
    session.add_all(rows)
    session.commit()
    store_fields(session, policy, rows, llm.extract_fields(policy.type, rows))
    return RedirectResponse(f"/policy/{policy.id}", status_code=303)


def store_fields(session: Session, policy: Policy, chunks: list[Chunk],
                 extraction: llm.Extraction | None) -> None:
    """Keep only what our code can verify. Every key field gets a row; unverified ones stay empty
    and the page shows "Not found — enter manually"."""
    by_id = {c.id: c.text for c in chunks}
    texts = list(by_id.values())
    found: dict[str, llm.ExtractedField] = {}
    for f in extraction.fields if extraction else []:
        if f.name in found or f.name not in llm.KEY_FIELDS[policy.type]:
            continue
        if f.chunk_id in by_id and verify_field(f.value, f.quote, by_id[f.chunk_id]):
            found[f.name] = f

    for name in llm.KEY_FIELDS[policy.type]:
        f = found.get(name)
        session.add(Field(policy_id=policy.id, name=name, value=f.value if f else "",
                          chunk_id=f.chunk_id if f else None, quote=f.quote if f else "", verified=bool(f)))
    if extraction:
        policy.insurer = extraction.insurer if appears_in(extraction.insurer, texts) else ""
        policy.claims_phone = extraction.claims_phone if appears_in(extraction.claims_phone, texts) else ""
        last4 = extraction.policy_number_last4
        policy.policy_number_last4 = last4 if len(last4) == 4 and appears_in("••••" + last4, texts) else ""
        session.add(policy)
    session.commit()


def own_policy(session: Session, hh_id: str, policy_id: int) -> Policy:
    policy = session.get(Policy, policy_id)
    if not policy or policy.household_id != hh_id:
        raise HTTPException(404)
    return policy


@router.get("/policy/{policy_id}", response_class=HTMLResponse)
def policy_page(policy_id: int, request: Request, session: SessionDep):
    hh_id = request.state.household.id
    policy = own_policy(session, hh_id, policy_id)
    member_ids = covers(session, hh_id).get(policy.id, set())
    names = [m.nickname for m in session.exec(select(Member).where(Member.id.in_(member_ids)))]
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
    )
