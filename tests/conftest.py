"""Runs before any test module imports the app: fresh test database, no real LLM calls."""

import os
import pathlib

TEST_DB = pathlib.Path("test.db")
TEST_DB.unlink(missing_ok=True)
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["ANTHROPIC_API_KEY"] = "test-key-not-real"  # load_dotenv() won't override it with the real one

import pytest  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def tables():
    from app.db import create_tables

    create_tables()


@pytest.fixture(autouse=True)
def no_real_llm(monkeypatch):
    """Tests never spend money: any real LLM call fails loudly. Tests that need answers patch llm.*."""
    from app.services import llm

    def blocked(*args, **kwargs):
        raise AssertionError("real LLM call in a test")

    monkeypatch.setattr(llm, "_parse", blocked)
    monkeypatch.setattr(llm, "extract_fields", lambda policy_type, chunks: None)
