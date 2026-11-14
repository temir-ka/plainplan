"""FastAPI entry point: app, guest-cookie middleware, routers, static files."""

import threading
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session
from starlette.concurrency import run_in_threadpool

from app import config
from app.db import create_tables, engine
from app.models import Household
from app.routes import ask, pages, policies, situation
from app.services import demo


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    if config.DEMO_FILE:  # fill the demo cache in the background; the app is usable meanwhile
        threading.Thread(target=demo.warm_cache, daemon=True).start()
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
        household = Household(id=str(uuid.uuid4()), is_demo=True)  # first visit opens the demo family
        session.add(household)
        session.commit()
        session.refresh(household)
        session.expunge(household)
        return household, True


def _ensure_demo(household: Household) -> Household:
    """Build this guest's copy of the demo family on their first page view."""
    with Session(engine) as session:
        if demo.needs_seed(session, household):
            demo.seed(session, household.id)
            household = session.get(Household, household.id)
            session.expunge(household)
    return household


@app.middleware("http")
async def guest_household(request: Request, call_next):
    if request.url.path.startswith("/static") or request.url.path in ("/health", "/favicon.ico"):
        return await call_next(request)

    # DB work runs in a thread so a slow first demo build doesn't block other visitors
    household, is_new = await run_in_threadpool(_get_or_create_household, request.cookies.get(config.COOKIE_NAME))
    if household.is_demo and request.method == "GET":
        household = await run_in_threadpool(_ensure_demo, household)
    request.state.household = household
    response = await call_next(request)
    route_set_cookie = any(
        h.startswith(f"{config.COOKIE_NAME}=") for h in response.headers.getlist("set-cookie")
    )
    if is_new and not route_set_cookie:  # /start and /delete-data set the cookie themselves
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
app.include_router(policies.router)
app.include_router(ask.router)
app.include_router(situation.router)
