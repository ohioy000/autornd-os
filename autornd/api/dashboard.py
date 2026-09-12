"""Workflow visibility dashboard — HTML served by FastAPI."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

dashboard_router = APIRouter()

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"


@dashboard_router.get("/", response_class=HTMLResponse)
async def dashboard():
    return (_TEMPLATE_DIR / "dashboard.html").read_text(encoding="utf-8")
