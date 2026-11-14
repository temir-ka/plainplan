from dataclasses import dataclass

from app.services.search import expand_query, mentioned_members, narrow_policy_types, search


@dataclass
class C:
    id: int
    text: str


CHUNKS = [
    C(1, "Orthodontics 50% covered after deductible (up to $1,000 per person per lifetime)"),
    C(2, "Annual Deductible $50 per person"),
    C(3, "Emergency room care 20% coinsurance"),
    C(4, "PART E — DUTIES AFTER AN ACCIDENT OR LOSS. We must be notified promptly."),
]


def test_braces_finds_orthodontics_via_synonyms():
    assert "orthodontics" in expand_query("Are Ava's braces covered?")
    assert search(CHUNKS, "Are Ava's braces covered?")[0].id == 1


def test_accident_question_finds_duties():
    assert search(CHUNKS, "what do I do after a car accident")[0].id == 4


def test_no_match_returns_nothing():
    assert search(CHUNKS, "pet insurance for our hamster") == []
    assert search([], "anything") == []


def test_policy_type_and_member_detection():
    assert narrow_policy_types("Are Ava's braces covered?") == {"dental"}
    assert narrow_policy_types("Someone hit our car") == {"auto"}
    assert narrow_policy_types("What is covered?") == set()
    assert mentioned_members("Are Ava’s braces covered?", {1: "Dad", 2: "Ava"}) == {2}
    assert mentioned_members("Is Avalon covered?", {2: "Ava"}) == set()  # whole word only
