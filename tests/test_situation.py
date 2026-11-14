"""Something happened? end to end with a fake LLM."""

import re

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.db import engine
from app.main import app
from app.models import Chunk, Policy, PolicyMember
from app.services import llm
from app.services.deadlines import find_deadline
from app.services.redflags import mentions_injury

AUTO_TEXT = ("PART E — DUTIES AFTER AN ACCIDENT OR LOSS\nWe must be notified promptly of how, when and where "
             "the accident or loss happened.")
HEALTH_TEXT = "If you need immediate medical attention: Emergency room care 20% coinsurance"
HOME_TEXT = "Send to us, within 60 days after our request, your signed, sworn proof of loss."


def member(client, nick, role="parent") -> int:
    html = client.post("/members", data={"nickname": nick, "role": role}).text
    return int(re.findall(r'hx-delete="/members/(\d+)"', html)[-1])


@pytest.fixture
def family():
    with TestClient(app) as client:
        client.get("/")
        hh = client.cookies["hh_id"]
        dad, ava = member(client, "Dad"), member(client, "Ava", "child")
        with Session(engine) as s:
            auto = Policy(household_id=hh, type="auto", insurer="Heartland", claims_phone="(800) 555-0199")
            health = Policy(household_id=hh, type="health", insurer="Sample Health Co.")
            home = Policy(household_id=hh, type="home", insurer="Sample Home")
            s.add_all([auto, health, home])
            s.flush()
            s.add(PolicyMember(policy_id=health.id, member_id=dad))
            chunks = {"auto": Chunk(policy_id=auto.id, page=3, text=AUTO_TEXT),
                      "health": Chunk(policy_id=health.id, page=2, text=HEALTH_TEXT),
                      "home": Chunk(policy_id=home.id, page=11, text=HOME_TEXT)}
            s.add_all(chunks.values())
            s.commit()
            ids = {k: c.id for k, c in chunks.items()}
        yield client, ids


def fake_llm(monkeypatch, situation, hurt, affected, steps_by_type, calls=None):
    monkeypatch.setattr(llm, "classify_situation", lambda text, nicks: llm.SituationGuess(
        situation=situation, emergency=False, someone_hurt=hurt, affected=affected))

    def steps(text, policy_type, chunks):
        if calls is not None:
            calls.append(policy_type)
        return llm.Steps(steps=steps_by_type.get(policy_type, []))
    monkeypatch.setattr(llm, "situation_steps", steps)


def post(client, text, member_id=""):
    return client.post("/situation", data={"text": text, "member_id": member_id}).text


def test_rear_ended_dad_neck_hurts(family, monkeypatch):
    client, ids = family
    calls = []
    fake_llm(monkeypatch, "car_accident", True, "", {
        "auto": [llm.Step(text="Tell the insurer promptly how, when and where it happened.", chunk_id=ids["auto"],
                          quote="We must be notified promptly of how, when and where the accident or loss happened."),
                 llm.Step(text="Send a police report within 5 days.", chunk_id=ids["auto"],  # invented
                          quote="You must send a police report within 5 days.")],
        "health": [llm.Step(text="ER care is 20% coinsurance under this plan.", chunk_id=ids["health"],
                            quote="Emergency room care 20% coinsurance")],
    }, calls)
    html = post(client, "Someone rear-ended our car and Dad's neck hurts")
    assert "call 911 first" in html
    assert "2 of your policies apply" in html and "Heartland · auto" in html and "Sample Health Co. · health" in html
    assert "Sample Home" not in html
    assert "how, when and where" in html and "police report within 5 days" not in html  # invented step dropped
    assert 'href="tel:(800) 555-0199"' in html
    assert "General checklist" in html and "other driver" in html
    assert sorted(calls) == ["auto", "health"]


def test_hurt_but_nobody_named_asks_who(family, monkeypatch):
    client, ids = family
    fake_llm(monkeypatch, "car_accident", True, "", {})
    html = post(client, "We were rear-ended and someone's neck hurts")
    assert "Who was hurt?" in html and ">Dad<" in html and ">Ava<" in html
    dad_id = re.search(r'name="member_id" value="(\d+)">\s*<button[^>]*>Dad<', html).group(1)
    html = post(client, "We were rear-ended and someone's neck hurts", member_id=dad_id)
    assert "Who was hurt?" not in html and "Sample Health Co." in html


def test_llm_cannot_invent_a_member(family, monkeypatch):
    client, _ = family
    fake_llm(monkeypatch, "car_accident", True, "Grandma", {})
    assert "Who was hurt?" in post(client, "rear-ended, grandma hurt her back")


def test_water_damage_shows_deadline(family, monkeypatch):
    client, ids = family
    fake_llm(monkeypatch, "water_damage", False, "", {
        "home": [llm.Step(text="Send a signed proof of loss within 60 days after they ask.", chunk_id=ids["home"],
                          quote="Send to us, within 60 days after our request, your signed, sworn proof of loss.")]})
    html = post(client, "A pipe burst in the basement")
    assert "call 911 first" not in html
    assert "Your policy says “within 60 days”" in html and "p. 11" in html


def test_llm_down_still_gives_checklist(family, monkeypatch):
    client, _ = family
    monkeypatch.setattr(llm, "classify_situation", lambda text, nicks: None)
    html = post(client, "something strange happened")
    assert "None of your policies clearly applies" in html and "General checklist" in html


def test_find_deadline_and_injury():
    assert find_deadline("within 60 days after our request") == "within 60 days"
    assert find_deadline("notify us promptly") == ""
    assert mentions_injury("Dad's neck hurts") and mentions_injury("Ava fell off her bike")
    assert not mentions_injury("a pipe burst in the basement")


def test_fragment_quote_is_not_enough(family, monkeypatch):
    client, ids = family
    fake_llm(monkeypatch, "car_accident", False, "", {
        "auto": [llm.Step(text="Call the plan's number before any visit.", chunk_id=ids["auto"], quote="We must be")]})
    html = post(client, "Someone hit our parked car")
    assert "before any visit" not in html and "couldn't find clear steps" in html
