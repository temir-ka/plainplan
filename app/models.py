"""Database tables.

Household -> Members (nickname + role only).
PolicyMember links a Policy to the Members it covers (a family health plan covers several people).
A Policy with no PolicyMember rows is Shared (house, car, anything jointly owned).
Chunk = one page of a policy's text. Field = one extracted key value with its verbatim quote.
"""

from datetime import date, datetime, timezone

from sqlmodel import Field as F
from sqlmodel import SQLModel


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Household(SQLModel, table=True):
    id: str = F(primary_key=True)  # the uuid4 stored in the hh_id cookie
    name: str = "My family"
    is_demo: bool = False
    is_paid: bool = False
    questions_used: int = 0
    created_at: datetime = F(default_factory=_now)


class Member(SQLModel, table=True):
    id: int | None = F(default=None, primary_key=True)
    household_id: str = F(foreign_key="household.id", index=True)
    nickname: str
    role: str  # "parent" | "child"


class Policy(SQLModel, table=True):
    id: int | None = F(default=None, primary_key=True)
    household_id: str = F(foreign_key="household.id", index=True)
    type: str  # "health" | "dental" | "auto" | "home"
    insurer: str = ""
    policy_number_last4: str = ""
    claims_phone: str = ""
    period_start: date | None = None
    period_end: date | None = None
    premium_monthly: float | None = None
    premium_due_day: int | None = None
    demo_values: bool = False  # insurer/phone/dates/premium typed from demo_family.json -> "Demo · entered by user"
    details_edited: bool = False  # the guest typed some of these details -> "entered by you"
    created_at: datetime = F(default_factory=_now)


class PolicyMember(SQLModel, table=True):
    policy_id: int = F(foreign_key="policy.id", primary_key=True)
    member_id: int = F(foreign_key="member.id", primary_key=True, index=True)


class Chunk(SQLModel, table=True):
    id: int | None = F(default=None, primary_key=True)
    policy_id: int = F(foreign_key="policy.id", index=True)
    page: int
    section: str = ""  # nearest heading above the chunk
    text: str


class Field(SQLModel, table=True):
    id: int | None = F(default=None, primary_key=True)
    policy_id: int = F(foreign_key="policy.id", index=True)
    name: str  # e.g. "deductible"
    value: str
    chunk_id: int | None = F(default=None, foreign_key="chunk.id")
    quote: str = ""  # verbatim text from the chunk
    verified: bool = False
    source: str = "extracted"  # "extracted" | "user" | "demo"


class DocCache(SQLModel, table=True):
    """Parsed chunks + raw LLM extraction per (file SHA-256, policy type). Same PDF -> no second LLM call.
    Holds only masked text and model output, never the file. Fields are still re-verified on every use."""
    key: str = F(primary_key=True)  # "<sha256>:<type>"
    chunks_json: str  # [{"page", "section", "text"}, ...]
    extraction_json: str  # llm.Extraction as JSON; chunk_id = index into chunks_json
