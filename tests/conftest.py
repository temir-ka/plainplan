"""Runs before any test module imports the app: point it at a fresh test database."""

import os
import pathlib

TEST_DB = pathlib.Path("test.db")
TEST_DB.unlink(missing_ok=True)
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"

import pytest  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def tables():
    from app.db import create_tables

    create_tables()
