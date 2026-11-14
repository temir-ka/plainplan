"""Red flags in the user's description -> show "call 911 first" banner.

Deliberately over-cautious: a false alarm costs one banner, a miss could cost much more.
"nobody was hurt" still shows the banner; that is fine.
"""

import re

BANNER = "If anyone is hurt or in danger, call 911 first."

_PATTERNS = [
    r"hurts?", r"hurting", r"injur\w*", r"pains?", r"painful",r"bleed\w*", r"blood\w*",
    r"unconscious", r"passed out", r"faint\w*", r"not breathing", r"can'?t breathe", r"choking",
    r"chest pain", r"heart attack", r"stroke", r"seizure\w*", r"overdos\w*",
    r"suicid\w*", r"kill (?:myself|himself|herself|themselves)",
    r"broken? (?:bone|arm|leg|neck|back)", r"head (?:injury|trauma)", r"hit (?:his|her|their|my) head",
    r"fire", r"burn\w*", r"smoke", r"gas leak", r"smell(?:s|ing)? gas", r"carbon monoxide",
    r"trapped", r"electrocut\w*", r"drown\w*", r"ambulance", r"911", r"emergency",
    r"weapon", r"gun", r"break-?in", r"intruder",
]
_RED_FLAG = re.compile(r"\b(?:" + "|".join(_PATTERNS) + r")\b", re.IGNORECASE)


def find_red_flags(text: str) -> list[str]:
    return [m.group(0).lower() for m in _RED_FLAG.finditer(text.replace("’", "'"))]


def show_911_banner(text: str, llm_emergency: bool = False) -> bool:
    return llm_emergency or bool(find_red_flags(text))
