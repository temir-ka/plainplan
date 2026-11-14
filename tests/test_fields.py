"""Key fields from the LLM are kept only when our code can verify them."""

from sqlmodel import Session, select

from app.db import engine
from app.models import Chunk, Field, Household, Policy
from app.routes.policies import store_fields
from app.services.citations import appears_in, verify_field
from app.services.llm import KEY_FIELDS, ExtractedField, Extraction

DENTAL_TEXT = ("Delta Dental PPO (Standard) Plan\nAnnual Deductible $50 per person\n"
               "Orthodontics: $1,000 lifetime maximum (dependent children only)\n"
               "Claims: call 1-800-765-6003. Member ID ••••4821")


def test_verify_field():
    assert verify_field("$50 per person", "Annual Deductible $50 per person", DENTAL_TEXT)
    assert not verify_field("$100 per person", "Annual Deductible $50 per person", DENTAL_TEXT)  # number
    assert not verify_field("$50", "Annual deductible is fifty dollars", DENTAL_TEXT)  # quote not in text


def test_appears_in():
    assert appears_in("Delta Dental", [DENTAL_TEXT])
    assert not appears_in("Aetna", [DENTAL_TEXT])
    assert not appears_in("", [DENTAL_TEXT])


def make_policy() -> tuple[Policy, list[Chunk]]:
    with Session(engine) as s:
        hh = Household(id="hh-fields-test", name="Test")
        s.merge(hh)
        policy = Policy(household_id=hh.id, type="dental")
        s.add(policy)
        s.flush()
        chunk = Chunk(policy_id=policy.id, page=1, text=DENTAL_TEXT)
        s.add(chunk)
        s.commit()
        s.refresh(policy)
        s.refresh(chunk)
        s.expunge_all()
        return policy, [chunk]


def test_store_fields_keeps_only_verified_values():
    policy, chunks = make_policy()
    cid = chunks[0].id
    extraction = Extraction(
        insurer="Delta Dental",
        claims_phone="1-800-765-6003",
        policy_number_last4="4821",
        fields=[
            ExtractedField(name="deductible", value="$50 per person", chunk_id=cid,
                           quote="Annual Deductible $50 per person"),
            ExtractedField(name="orthodontia", value="$1,500 lifetime max", chunk_id=cid,  # wrong number
                           quote="Orthodontics: $1,000 lifetime maximum (dependent children only)"),
            ExtractedField(name="annual_maximum", value="$2,000", chunk_id=cid,
                           quote="Annual maximum $2,000"),  # invented quote
            ExtractedField(name="favorite_color", value="blue", chunk_id=cid, quote="Delta Dental PPO"),
        ],
    )
    with Session(engine) as s:
        s.add(policy)
        store_fields(s, policy, chunks, extraction)
        fields = {f.name: f for f in s.exec(select(Field).where(Field.policy_id == policy.id))}
        s.refresh(policy)
        insurer, phone, last4 = policy.insurer, policy.claims_phone, policy.policy_number_last4

    assert set(fields) == set(KEY_FIELDS["dental"])  # one row per key field, nothing extra
    assert fields["deductible"].verified and fields["deductible"].value == "$50 per person"
    assert not fields["orthodontia"].verified and fields["orthodontia"].value == ""
    assert not fields["annual_maximum"].verified
    assert (insurer, phone, last4) == ("Delta Dental", "1-800-765-6003", "4821")


def test_store_fields_drops_insurer_not_in_document():
    policy, chunks = make_policy()
    with Session(engine) as s:
        s.add(policy)
        store_fields(s, policy, chunks, Extraction(insurer="Aetna", claims_phone="1-800-555-0000",
                                                   policy_number_last4="9999", fields=[]))
        s.refresh(policy)
        assert (policy.insurer, policy.claims_phone, policy.policy_number_last4) == ("", "", "")


def test_llm_failure_leaves_all_fields_not_found():
    policy, chunks = make_policy()
    with Session(engine) as s:
        s.add(policy)
        store_fields(s, policy, chunks, None)
        fields = s.exec(select(Field).where(Field.policy_id == policy.id)).all()
    assert len(fields) == len(KEY_FIELDS["dental"]) and not any(f.verified for f in fields)
