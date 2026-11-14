"""Demo family: first visit opens The Parkers, built through the same pipeline, cached by file hash."""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app import config
from app.db import engine
from app.main import app
from app.models import DocCache, Field, Policy
from app.services import llm

pytestmark = pytest.mark.skipif(
    not __import__("pathlib").Path("samples/demo_family.json").exists(), reason="demo JSON not present")


@pytest.fixture
def demo_on(monkeypatch):
    monkeypatch.setattr(config, "DEMO_FILE", "samples/demo_family.json")
    calls = []

    def fake_extract(policy_type, chunks):
        calls.append(policy_type)
        first = chunks[0]
        quote = first.text.splitlines()[0]
        return llm.Extraction(insurer="", claims_phone="", policy_number_last4="", fields=[
            llm.ExtractedField(name=llm.KEY_FIELDS[policy_type][0], value="see quote", chunk_id=first.id, quote=quote)])

    monkeypatch.setattr(llm, "extract_fields", fake_extract)
    return calls


def test_first_visit_opens_the_parkers(demo_on):
    with TestClient(app) as client:
        html = client.get("/").text
        assert "The Parkers" in html and "Demo family." in html and "Start my own family" in html
        for nick in ("Mom", "Dad", "Leo", "Ava"):
            assert nick in html
        hh = client.cookies["hh_id"]

    with Session(engine) as s:
        policies = s.exec(select(Policy).where(Policy.household_id == hh)).all()
        assert len(policies) == 6 and all(p.demo_values for p in policies)
        health = next(p for p in policies if p.insurer == "Sample Health Co.")
        assert health.claims_phone == "1-800-555-0100"
        verified = s.exec(select(Field).where(Field.policy_id == health.id, Field.verified == True)).all()  # noqa: E712
        assert len(verified) == 1  # the fake field passed the same quote check as real ones


def test_second_guest_uses_cache_no_llm_calls(demo_on):
    with TestClient(app) as first:
        first.get("/")
    calls_after_first = len(demo_on)
    with TestClient(app) as second:
        assert "The Parkers" in second.get("/").text
    assert len(demo_on) == calls_after_first  # everything came from DocCache
    with Session(engine) as s:
        assert len(s.exec(select(DocCache)).all()) >= 6


def test_start_my_own_family_leaves_the_demo(demo_on):
    with TestClient(app) as client:
        client.get("/")
        client.post("/start", data={"name": "The Smiths"})
        html = client.get("/").text
        assert "The Smiths" in html and "Demo family." not in html and "Ava" not in html
