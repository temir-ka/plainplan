"""/situation flow (Something happened?). Page stub until classification + steps are in."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.routes.pages import render

router = APIRouter()


@router.get("/situation", response_class=HTMLResponse)
def situation_page(request: Request):
    return render(request, "situation.html")
