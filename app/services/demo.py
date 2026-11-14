"""Demo family ("The Parkers") from samples/demo_family.json.

The first visit opens the demo family. Each guest gets their own copy, built through the same
ingest pipeline as an upload. Thanks to DocCache, only the very first run calls the LLM:
`python -m app.services.demo` (or the startup warm-up) fills the cache in parallel.
"""

import json
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

from sqlmodel import Session, select

from app import config
from app.db import engine
from app.models import Household, Member, Policy, PolicyMember
from app.services.ingest import read_and_extract, save_document

log = logging.getLogger(__name__)


def _load() -> dict | None:
    path = Path(config.DEMO_FILE) if config.DEMO_FILE else None
    if not path or not path.exists():
        return None
    return json.loads(path.read_text())


def _pdf(entry: dict) -> Path:
    return Path(config.DEMO_FILE).parent / entry["file"]


def _date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def needs_seed(session: Session, household: Household) -> bool:
    if not household.is_demo or _load() is None:
        return False
    return session.exec(select(Policy).where(Policy.household_id == household.id)).first() is None


def seed(session: Session, household_id: str) -> None:
    data = _load()
    # Read every document first (may write DocCache and commit), THEN build the family in one go.
    docs = [(entry, *read_and_extract(session, _pdf(entry), entry["type"])) for entry in data["policies"]]

    household = session.get(Household, household_id)
    household.name = data["household"]
    session.add(household)

    members = {}
    for m in data["members"]:
        member = Member(household_id=household_id, nickname=m["nickname"], role=m["role"])
        session.add(member)
        members[m["nickname"]] = member
    session.flush()

    for entry, chunks, extraction in docs:
        policy = Policy(
            household_id=household_id, type=entry["type"], demo_values=True,
            insurer=entry.get("insurer", ""), claims_phone=entry.get("claims_phone", ""),
            period_start=_date(entry.get("period_start")), period_end=_date(entry.get("period_end")),
            premium_monthly=entry.get("premium_monthly"), premium_due_day=entry.get("premium_due_day"),
        )
        session.add(policy)
        session.flush()
        session.add_all(PolicyMember(policy_id=policy.id, member_id=members[n].id) for n in entry["covers"])
        save_document(session, policy, chunks, extraction)


def warm_cache() -> None:
    """Parse + extract every demo document once, in parallel, so guests never wait for the LLM."""
    data = _load()
    if data is None:
        return

    def one(entry: dict) -> None:
        with Session(engine) as session:
            read_and_extract(session, _pdf(entry), entry["type"])

    with ThreadPoolExecutor(max_workers=2) as pool:  # 2 at a time: keeps memory low on a 1 GB server
        for entry, result in zip(data["policies"], pool.map(lambda e: _safe(one, e), data["policies"])):
            log.info("demo cache %s: %s", entry["file"], result)


def _safe(fn, entry) -> str:
    try:
        fn(entry)
        return "ok"
    except Exception as e:  # never crash the app because of the demo
        log.warning("demo cache failed for %s: %s", entry["file"], e)
        return f"failed: {e}"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from app.db import create_tables

    create_tables()
    warm_cache()
