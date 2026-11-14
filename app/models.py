"""Database tables.

Household -> Members (nickname + role only).
Policy belongs to a Member, or is Shared when member_id is NULL.
Chunk = one page of a policy's text. Field = one extracted key value with its verbatim quote.
"""

from datetime import datetime, timezone

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
    role: str  # "Parent" | "Child"


class Policy(SQLModel, table=True):
    id: int | None = F(default=None, primary_key=True)
    household_id: str = F(foreign_key="household.id", index=True)
    member_id: int | None = F(default=None, foreign_key="member.id")  # None = Shared
    type: str  # "health" | "dental" | "auto" | "home"
    insurer: str = ""
    policy_number_last4: str = ""
    claims_phone: str = ""
    created_at: datetime = F(default_factory=_now)


class Chunk(SQLModel, table=True):
    id: int | None = F(default=None, primary_key=True)
    policy_id: int = F(foreign_key="policy.id", index=True)
    page: int
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
