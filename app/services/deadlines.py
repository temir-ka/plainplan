"""Deadlines. For now: find a deadline inside a verified policy quote ("within 60 days").
The Next 90 days feed comes later."""

import re

_WITHIN = re.compile(r"\bwithin\s+(\d{1,3})\s+(day|days|hour|hours)\b", re.IGNORECASE)


def find_deadline(quote: str) -> str:
    """'...send us, within 60 days after our request, your proof of loss' -> 'within 60 days'. '' if none."""
    m = _WITHIN.search(quote)
    return f"within {m.group(1)} {m.group(2).lower()}" if m else ""
