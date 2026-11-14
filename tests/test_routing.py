from dataclasses import dataclass

from app.services.routing import ROUTES, SITUATIONS, route

MOM, DAD, LEO, AVA = 1, 2, 3, 4


@dataclass
class P:
    id: int
    type: str


FAMILY = [
    P(10, "auto"),     # shared car
    P(11, "home"),     # shared house
    P(12, "health"),   # family plan: Dad, Leo, Ava
    P(13, "health"),   # Mom's own plan from her employer
    P(14, "dental"),   # Ava only
]
COVERS = {12: {DAD, LEO, AVA}, 13: {MOM}, 14: {AVA}}


def ids(result) -> list[int]:
    return [p.id for p in result.policies]


def test_every_situation_has_a_route():
    assert set(ROUTES) == set(SITUATIONS)


def test_car_accident_with_dad_hurt_uses_family_plan():
    result = route("car_accident", FAMILY, COVERS, someone_hurt=True, member_id=DAD)
    assert ids(result) == [10, 12]  # auto + the family plan that covers Dad, not Mom's plan
    assert not result.needs_person


def test_car_accident_with_mom_hurt_uses_her_own_plan():
    assert ids(route("car_accident", FAMILY, COVERS, someone_hurt=True, member_id=MOM)) == [10, 13]


def test_car_accident_nobody_hurt_is_auto_only():
    assert ids(route("car_accident", FAMILY, COVERS)) == [10]


def test_hurt_but_no_member_named_asks_who():
    result = route("car_accident", FAMILY, COVERS, someone_hurt=True)
    assert ids(result) == [10]
    assert result.needs_person


def test_dental_problem_always_needs_a_person():
    assert route("dental_problem", FAMILY, COVERS).needs_person
    assert ids(route("dental_problem", FAMILY, COVERS, member_id=AVA)) == [14, 12]


def test_member_without_dental_gets_only_health():
    assert ids(route("dental_problem", FAMILY, COVERS, member_id=LEO)) == [12]


def test_water_damage_and_theft():
    assert ids(route("water_damage", FAMILY, COVERS)) == [11]
    assert ids(route("theft", FAMILY, COVERS)) == [11, 10]


def test_unknown_or_other_situation_routes_nowhere():
    assert ids(route("other", FAMILY, COVERS)) == []
    assert ids(route("alien_abduction", FAMILY, COVERS)) == []
