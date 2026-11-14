import pytest

from app.services.redflags import find_red_flags, show_911_banner


@pytest.mark.parametrize("text", [
    "Someone rear-ended our car and Dad's neck hurts",
    "Ava fell and is bleeding",
    "My husband has chest pain",
    "Kitchen fire, smoke everywhere",
    "I smell gas in the basement",
    "He can’t breathe",
    "Grandpa passed out",
])
def test_red_flags_trigger_banner(text):
    assert show_911_banner(text)


@pytest.mark.parametrize("text", [
    "A pipe burst and the basement is flooded",
    "Someone stole my bike from the garage",
    "Hail dented the car roof",
    "Are Ava's braces covered?",
])
def test_no_red_flags(text):
    assert not show_911_banner(text)


def test_llm_emergency_flag_alone_shows_banner():
    assert show_911_banner("something odd happened", llm_emergency=True)


def test_no_false_match_inside_words():
    assert find_red_flags("painting the gunwale of the boat") == []
