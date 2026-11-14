"""Situation type -> which of the family's policies apply. A plain dict, not an LLM call.

Asset policies (auto, home) apply whoever owns them.
Personal policies (health, dental) apply only to the member who was affected.
"""

from dataclasses import dataclass, field
from typing import Protocol

SITUATIONS = (
    "car_accident",
    "water_damage",
    "fire",
    "theft",
    "storm_damage",
    "dental_problem",
    "illness",
    "injury",
    "other",
)

# Policy types in the order we show them.
ROUTES: dict[str, list[str]] = {
    "car_accident": ["auto", "health"],
    "water_damage": ["home"],
    "fire": ["home"],
    "theft": ["home", "auto"],
    "storm_damage": ["home", "auto"],
    "dental_problem": ["dental", "health"],
    "illness": ["health"],
    "injury": ["health"],
    "other": [],
}

PERSONAL_TYPES = {"health", "dental"}
# Situations where a person is always affected, even without an explicit "hurt".
ALWAYS_PERSONAL = {"dental_problem", "illness", "injury"}


class PolicyLike(Protocol):
    id: int | None
    type: str
    member_id: int | None


@dataclass
class RoutingResult:
    policies: list = field(default_factory=list)
    needs_person: bool = False  # ask "Who was hurt?" with member buttons


def route(
    situation: str,
    policies: list[PolicyLike],
    someone_hurt: bool = False,
    member_id: int | None = None,
) -> RoutingResult:
    types = ROUTES.get(situation, [])
    person_involved = someone_hurt or situation in ALWAYS_PERSONAL
    result = RoutingResult()

    for policy_type in types:
        if policy_type in PERSONAL_TYPES:
            if not person_involved:
                continue
            if member_id is None:
                result.needs_person = True
                continue
            matches = [p for p in policies if p.type == policy_type and p.member_id == member_id]
        else:
            matches = [p for p in policies if p.type == policy_type]
        result.policies.extend(matches)

    return result
