"""FastAPI entry point: app, guest-cookie middleware, routers, static files."""

import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session

from app import config
from app.db import create_tables, engine
from app.models import Household
from app.routes import pages


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    yield


app = FastAPI(title="Plainplan", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


def _get_or_create_household(hh_id: str | None) -> tuple[Household, bool]:
    """Return the guest's household and whether a new cookie must be set."""
    with Session(engine) as session:
        if hh_id:
            household = session.get(Household, hh_id)
            if household:
                session.expunge(household)
                return household, False
        household = Household(id=str(uuid.uuid4()))
        session.add(household)
        session.commit()
        session.refresh(household)
        session.expunge(household)
        return household, True


@app.middleware("http")
async def guest_household(request: Request, call_next):
    if request.url.path.startswith("/static") or request.url.path == "/health":
        return await call_next(request)

    household, is_new = _get_or_create_household(request.cookies.get(config.COOKIE_NAME))
    request.state.household = household
    response = await call_next(request)
    if is_new:
        response.set_cookie(
            config.COOKIE_NAME,
            household.id,
            max_age=config.COOKIE_MAX_AGE,
            httponly=True,
            samesite="lax",
            secure=config.BASE_URL.startswith("https"),
        )
    return response


@app.get("/health")
def health() -> dict:
    return {"ok": True}


app.include_router(pages.router)
