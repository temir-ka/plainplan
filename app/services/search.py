"""BM25 search over policy chunks (rank_bm25). Pure Python, no LLM.

The caller decides WHICH chunks may be searched (the scope); this module only ranks them.
For household questions, `narrow_policy_types` / `mentioned_members` help pick the right policies.
"""

import re
from collections.abc import Sequence
from typing import Protocol

from rank_bm25 import BM25Okapi

TOP_K = 6

_STOPWORDS = set(
    "a an and are as at be but by can do does for from has have how i if in is it its my of on or our "
    "so that the their them they this to us was we what when where which who will with you your".split()
)

# Everyday words -> words policies actually use. Added to the query, not replacing it.
SYNONYMS: dict[str, list[str]] = {
    "braces": ["orthodontia", "orthodontics", "orthodontic"],
    "teeth": ["dental", "tooth"], "dentist": ["dental"], "cleaning": ["preventive", "cleanings"],
    "er": ["emergency", "room"], "hospital": ["inpatient", "emergency", "hospital"],
    "doctor": ["physician", "office", "visit"], "pills": ["drugs", "prescription"],
    "meds": ["drugs", "prescription"], "medicine": ["drugs", "prescription"],
    "car": ["auto", "vehicle"], "crash": ["collision", "accident"], "rental": ["rental", "transportation"],
    "tow": ["towing"], "stolen": ["theft"], "flood": ["water", "flood"], "leak": ["water", "discharge"],
    "pipe": ["water", "plumbing"], "house": ["dwelling"], "stuff": ["personal", "property"],
}

POLICY_TYPE_WORDS: dict[str, set[str]] = {
    "dental": {"dental", "dentist", "teeth", "tooth", "braces", "orthodontia", "orthodontics", "cleaning",
               "filling", "fillings", "crown", "crowns", "cavity", "root", "canal", "implant"},
    "health": {"doctor", "hospital", "er", "emergency", "urgent", "prescription", "drug", "drugs", "meds",
               "specialist", "surgery", "therapy", "pregnancy", "baby", "x-ray", "mri", "ambulance"},
    "auto": {"car", "auto", "vehicle", "accident", "collision", "crash", "tow", "towing", "rental",
             "driver", "windshield", "truck"},
    "home": {"home", "house", "roof", "water", "pipe", "leak", "flood", "fire", "theft", "stolen",
             "burglary", "dwelling", "basement", "storm", "hail", "tree"},
}


class ChunkLike(Protocol):
    id: int | None
    text: str


def tokenize(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)?", text.lower().replace("’", "'"))
    return [w for w in words if w not in _STOPWORDS]


def expand_query(question: str) -> list[str]:
    tokens = tokenize(question)
    return tokens + [syn for t in tokens for syn in SYNONYMS.get(t, [])]


def narrow_policy_types(question: str) -> set[str]:
    words = set(tokenize(question))
    return {ptype for ptype, vocab in POLICY_TYPE_WORDS.items() if words & vocab}


def mentioned_members(question: str, nicknames: dict[int, str]) -> set[int]:
    """'Are Ava's braces covered?' -> {id of Ava}. Whole-word, case-insensitive."""
    q = question.lower().replace("’", "'")
    return {mid for mid, nick in nicknames.items() if re.search(rf"\b{re.escape(nick.lower())}\b", q)}


# Words in almost every question; they rank but never make a chunk "match" on their own.
_WEAK = {"cover", "covered", "coverage", "covers", "policy", "plan", "pay", "paid", "insurance", "much", "get"}


def search(chunks: Sequence[ChunkLike], question: str, k: int = TOP_K) -> list:
    """Chunks sharing at least one meaningful word with the question, best BM25 score first.
    (On tiny corpora BM25 scores can be negative, so we don't filter on score > 0.)"""
    if not chunks:
        return []
    query = expand_query(question)
    strong = set(query) - _WEAK
    docs = [tokenize(c.text) or ["_"] for c in chunks]
    scores = BM25Okapi(docs).get_scores(query)
    matches = [i for i, doc in enumerate(docs) if strong & set(doc)]
    matches.sort(key=lambda i: (-scores[i], i))
    return [chunks[i] for i in matches[:k]]
