"""/ask endpoint (scope: household | member:{id} | shared | policy:{id}). Stub until search + LLM are in."""

from typing import Annotated

from fastapi import APIRouter, Form
from fastapi.responses import HTMLResponse

router = APIRouter()


@router.post("/ask", response_class=HTMLResponse)
def ask(q: Annotated[str, Form()] = "", scope: Annotated[str, Form()] = "household"):
    return HTMLResponse('<p class="text-sm text-slate-500">Answers are coming soon.</p>')
