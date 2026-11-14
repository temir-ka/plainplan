"""Settings read from environment variables. Secrets never live in code."""

import os

from dotenv import load_dotenv

load_dotenv()  # reads a local .env if present (ignored by git)

DATABASE_URL: str = os.getenv("DATABASE_URL") or "sqlite:///local.db"
BASE_URL: str = os.getenv("BASE_URL", "http://localhost:8000")
COOKIE_NAME = "hh_id"
COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30 days, matches guest data retention
