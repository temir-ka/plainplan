"""Situation type -> which of the family's policies apply. A plain dict, not an LLM call.

Asset policies (auto, home) apply whoever owns them.
Personal policies (health, dental) apply only if they cover the member who was affected
(`covers` maps policy_id -> member ids, so one family plan can cover several people).
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


@dataclass
class RoutingResult:
    policies: list = field(default_factory=list)
    needs_person: bool = False  # ask "Who was hurt?" with member buttons


def route(
    situation: str,
    policies: list[PolicyLike],
    covers: dict[int, set[int]],
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
            matches = [p for p in policies
                       if p.type == policy_type and member_id in covers.get(p.id, set())]
        else:
            matches = [p for p in policies if p.type == policy_type]
        result.policies.extend(matches)

    return result


# "General checklist (not from your policy)": plain templates, shown under the policy steps.
CHECKLISTS: dict[str, list[str]] = {
    "car_accident": [
        "Take photos of all cars, plates and the scene.",
        "Get the other driver's name, phone, insurer and policy number.",
        "Write down the police report number, if police came.",
        "Get names and phones of witnesses.",
        "Write down what happened while you remember it.",
    ],
    "water_damage": [
        "If it is safe, stop the water at the source or the main valve.",
        "Take photos and video before you clean up.",
        "Keep damaged items until the insurer has seen them.",
        "Keep receipts for emergency repairs, fans, and anything you buy.",
    ],
    "fire": [
        "Once everyone is safe, take photos and video of the damage.",
        "List damaged items with rough age and price.",
        "Keep receipts for a hotel, meals and other extra costs.",
    ],
    "theft": [
        "Report it to the police and keep the report number.",
        "List what was taken, with photos or receipts if you have them.",
        "Change locks or cancel cards if keys or wallets were taken.",
    ],
    "storm_damage": [
        "Take photos of the damage from several angles.",
        "Make only temporary repairs to stop more damage, and keep the receipts.",
        "Write down the date and time of the storm.",
    ],
    "dental_problem": [
        "Keep the dentist's notes, X-ray references and every receipt.",
        "Ask the dentist's office if they will send a pre-treatment estimate to the insurer.",
    ],
    "illness": ["Keep every bill and the Explanation of Benefits (EOB) you receive.",
                "Write down the dates of each visit."],
    "injury": ["Keep every bill and the Explanation of Benefits (EOB) you receive.",
               "Write down when and how the injury happened."],
    "other": ["Write down what happened and when.", "Take photos and keep receipts."],
}
