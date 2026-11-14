"""Database engine and session helper."""

from collections.abc import Iterator

from sqlmodel import Session, SQLModel, create_engine

from app import config


_url = config.DATABASE_URL
_connect_args = {"check_same_thread": False} if _url.startswith("sqlite") else {}
engine = create_engine(_url, connect_args=_connect_args, pool_pre_ping=True)


def create_tables() -> None:
    from app import models  # noqa: F401  (import registers the tables)

    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
