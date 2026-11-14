from dataclasses import dataclass

from app.services.routing import ROUTES, SITUATIONS, route

DAD, AVA = 1, 2


@dataclass
class P:
    id: int
    type: str
    member_id: int | None


FAMILY = [
    P(10, "auto", None),       # shared car
    P(11, "home", None),       # shared house
    P(12, "health", DAD),
    P(13, "health", AVA),
    P(14, "dental", AVA),
]


def ids(result) -> list[int]:
    return [p.id for p in result.policies]


def test_every_situation_has_a_route():
    assert set(ROUTES) == set(SITUATIONS)


def test_car_accident_with_dad_hurt():
    result = route("car_accident", FAMILY, someone_hurt=True, member_id=DAD)
    assert ids(result) == [10, 12]  # auto + Dad's health, not Ava's
    assert not result.needs_person


def test_car_accident_nobody_hurt_is_auto_only():
    assert ids(route("car_accident", FAMILY)) == [10]


def test_hurt_but_no_member_named_asks_who():
    result = route("car_accident", FAMILY, someone_hurt=True)
    assert ids(result) == [10]
    assert result.needs_person


def test_dental_problem_always_needs_a_person():
    assert route("dental_problem", FAMILY).needs_person
    assert ids(route("dental_problem", FAMILY, member_id=AVA)) == [14, 13]


def test_member_without_dental_gets_only_health():
    assert ids(route("dental_problem", FAMILY, member_id=DAD)) == [12]


def test_water_damage_and_theft():
    assert ids(route("water_damage", FAMILY)) == [11]
    assert ids(route("theft", FAMILY)) == [11, 10]


def test_unknown_or_other_situation_routes_nowhere():
    assert ids(route("other", FAMILY)) == []
    assert ids(route("alien_abduction", FAMILY)) == []
