"""Check that quotes really exist in the policy text. Pure Python, no LLM.

Rules (CLAUDE.md):
- a quote is valid only if it appears in its chunk after normalization
  (case, whitespace, curly quotes, dashes, PDF ligatures and line-break hyphens);
- every number in the answer must appear in at least one verified quote;
- nothing verifies -> the caller shows a refusal.
"""

import re
import unicodedata
from dataclasses import dataclass, field

MIN_QUOTE_CHARS = 8  # "50%" alone proves nothing

_QUOTES = str.maketrans({"‘": "'", "’": "'", "‚": "'", "‛": "'",
                         "“": '"', "”": '"', "„": '"', "‟": '"'})
_DASHES = re.compile(r"[‐‑‒–—―−]")
_LINE_BREAK_HYPHEN = re.compile(r"(\w)-\s*\n\s*(\w)")
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
_EDGE_PUNCT = " \t\n\"'.,;:…"


@dataclass
class Citation:
    chunk_id: int
    quote: str


@dataclass
class Verification:
    ok: bool
    verified: list[Citation] = field(default_factory=list)
    missing_numbers: list[str] = field(default_factory=list)


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)  # ligatures (ﬁ -> fi), non-breaking spaces
    text = text.replace("­", "")  # soft hyphen
    text = _LINE_BREAK_HYPHEN.sub(r"\1\2", text)  # "deduct-\nible" -> "deductible"
    text = text.translate(_QUOTES)
    text = _DASHES.sub("-", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


def quote_in_chunk(quote: str, chunk_text: str) -> bool:
    needle = normalize(quote).strip(_EDGE_PUNCT)
    if len(needle) < MIN_QUOTE_CHARS:
        return False
    return needle in normalize(chunk_text)


def numbers_in(text: str) -> set[str]:
    """'$1,500.00' -> '1500', '50%' -> '50', '1.5' -> '1.5'."""
    result = set()
    for raw in _NUMBER.findall(normalize(text)):
        number = raw.replace(",", "")
        if "." in number:
            number = number.rstrip("0").rstrip(".")
        result.add(number)
    return result


def verify(answer: str, citations: list[Citation], chunk_texts: dict[int, str]) -> Verification:
    verified = [
        c for c in citations
        if c.chunk_id in chunk_texts and quote_in_chunk(c.quote, chunk_texts[c.chunk_id])
    ]
    quoted_numbers: set[str] = set()
    for c in verified:
        quoted_numbers |= numbers_in(c.quote)
    missing = sorted(numbers_in(answer) - quoted_numbers)
    return Verification(ok=bool(verified) and not missing, verified=verified, missing_numbers=missing)
