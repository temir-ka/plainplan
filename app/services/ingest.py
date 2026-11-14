"""One pipeline for every policy document, uploaded or demo:

PDF -> masked page chunks (pdf.py) -> LLM key fields (llm.py) -> keep only verified fields (citations.py).

Results are cached by file SHA-256 + policy type (DocCache), so the same PDF never costs a second LLM call.
"""

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from app.models import Chunk, DocCache, Field, Policy
from app.services import llm
from app.services.citations import appears_in, verify_field
from app.services.pdf import PageChunk, read_policy_pdf


@dataclass
class _IndexedChunk:  # what the LLM sees before chunks have database ids: id = position in the list
    id: int
    page: int
    section: str
    text: str


def cache_key(pdf_bytes: bytes, policy_type: str) -> str:
    return f"{hashlib.sha256(pdf_bytes).hexdigest()}:{policy_type}"


def read_and_extract(session: Session, pdf_path: Path, policy_type: str) -> tuple[list[PageChunk], llm.Extraction | None]:
    """Raises pdf.ScannedPdfError for scans. Only successful extractions are cached."""
    key = cache_key(pdf_path.read_bytes(), policy_type)
    cached = session.get(DocCache, key)
    if cached:
        chunks = [PageChunk(**c) for c in json.loads(cached.chunks_json)]
        return chunks, llm.Extraction.model_validate_json(cached.extraction_json)

    chunks = read_policy_pdf(pdf_path)
    indexed = [_IndexedChunk(i, c.page, c.section, c.text) for i, c in enumerate(chunks)]
    extraction = llm.extract_fields(policy_type, indexed)
    if extraction is not None:
        _save_cache(session, key, chunks, extraction)
    return chunks, extraction


def _save_cache(session: Session, key: str, chunks: list[PageChunk], extraction: llm.Extraction) -> None:
    """Best effort: two requests may extract the same file at once (e.g. startup warm-up + first visitor).
    Callers must not have unsaved work in `session` when calling read_and_extract."""
    try:
        session.merge(DocCache(key=key, chunks_json=json.dumps([asdict(c) for c in chunks]),
                               extraction_json=extraction.model_dump_json()))
        session.commit()
    except SQLAlchemyError:
        session.rollback()  # someone else cached it first, or the DB was busy: same result, nothing lost


def save_document(session: Session, policy: Policy, chunks: list[PageChunk],
                  extraction: llm.Extraction | None) -> None:
    """Store chunks for an already-added policy, then its verified key fields."""
    rows = [Chunk(policy_id=policy.id, page=c.page, section=c.section, text=c.text) for c in chunks]
    session.add_all(rows)
    session.flush()  # rows get ids
    if extraction:
        extraction = extraction.model_copy(deep=True)
        for f in extraction.fields:  # index in the list -> real chunk id
            f.chunk_id = rows[f.chunk_id].id if 0 <= f.chunk_id < len(rows) else -1
    store_fields(session, policy, rows, extraction)


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
        # Values the user (or demo JSON) already entered win; extracted ones must appear in the document.
        if not policy.insurer and appears_in(extraction.insurer, texts):
            policy.insurer = extraction.insurer
        if not policy.claims_phone and appears_in(extraction.claims_phone, texts):
            policy.claims_phone = extraction.claims_phone
        last4 = extraction.policy_number_last4
        if len(last4) == 4 and appears_in("••••" + last4, texts):
            policy.policy_number_last4 = last4
        session.add(policy)
    session.commit()
