"""Manual edits: a typed value is marked "Entered by you" and is never shown as verified."""

import re
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.db import engine
from app.main import app
from app.models import Chunk, Field, Policy


@pytest.fixture
def setup():
    with TestClient(app) as client:
        client.get("/")
        hh = client.cookies["hh_id"]
        with Session(engine) as s:
            policy = Policy(household_id=hh, type="dental")
            s.add(policy)
            s.flush()
            chunk = Chunk(policy_id=policy.id, page=2, text="Annual Deductible $50 per person")
            s.add(chunk)
            s.flush()
            field = Field(policy_id=policy.id, name="deductible", value="$50 per person", chunk_id=chunk.id,
                          quote="Annual Deductible $50 per person", verified=True)
            empty = Field(policy_id=policy.id, name="annual_maximum", value="")
            s.add_all([field, empty])
            s.commit()
            yield client, policy.id, field.id, empty.id


def test_policy_page_shows_verified_and_not_found(setup):
    client, policy_id, _, _ = setup
    html = client.get(f"/policy/{policy_id}").text
    assert "Verified · p. 2" in html and "Enter manually" in html


def test_editing_a_field_marks_it_entered_by_you(setup):
    client, policy_id, field_id, empty_id = setup
    assert 'name="value"' in client.get(f"/fields/{field_id}/edit").text
    html = client.post(f"/fields/{field_id}", data={"value": "$75 per person"}).text
    assert "$75 per person" in html and "Entered by you" in html and "verified" not in html
    html = client.post(f"/fields/{empty_id}", data={"value": "$1,500"}).text
    assert "$1,500" in html and "Entered by you" in html
    with Session(engine) as s:
        f = s.get(Field, field_id)
        assert (f.source, f.verified, f.quote, f.chunk_id) == ("user", False, "", None)


def test_other_family_cannot_edit(setup):
    _, _, field_id, _ = setup
    with TestClient(app) as other:
        other.get("/")
        assert other.get(f"/fields/{field_id}/edit").status_code == 404
        assert other.post(f"/fields/{field_id}", data={"value": "hacked"}).status_code == 404


def test_save_details(setup):
    client, policy_id, _, _ = setup
    form = {"insurer": "Delta Dental", "claims_phone": "1-800-555-0100", "period_start": "2026-01-01",
            "period_end": "2026-12-31", "premium_monthly": "38.50", "premium_due_day": "1"}
    html = client.post(f"/policy/{policy_id}/details", data=form).text  # follows the redirect
    assert "Delta Dental" in html and "Dec 31, 2026" in html and "/ month" in html
    assert "Some details entered by you" in html
    with Session(engine) as s:
        p = s.get(Policy, policy_id)
        assert (p.period_end, p.premium_monthly, p.premium_due_day) == (date(2026, 12, 31), 38.5, 1)


@pytest.mark.parametrize("bad, message", [
    ({"period_start": "2026-12-31", "period_end": "2026-01-01"}, "end date is before"),
    ({"premium_monthly": "-5"}, "premium looks wrong"),
    ({"premium_due_day": "40"}, "between 1 and 31"),
    ({"premium_monthly": "lots"}, "Check the dates and numbers"),
])
def test_bad_details_show_error_and_save_nothing(setup, bad, message):
    client, policy_id, _, _ = setup
    form = {"insurer": "X", "claims_phone": "", "period_start": "", "period_end": "",
            "premium_monthly": "", "premium_due_day": "", **bad}
    html = client.post(f"/policy/{policy_id}/details", data=form).text
    assert message in html
    with Session(engine) as s:
        assert s.get(Policy, policy_id).insurer == ""
