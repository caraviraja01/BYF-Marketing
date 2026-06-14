"""FastAPI app: the dashboard, the human-review gate, and the analytics view."""
from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from .brand import load_brand
from .db import get_session, init_db
from .llm import get_llm
from .models import ContentItem, ItemStatus, PipelineRun
from .orchestrator import Orchestrator

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app = FastAPI(title="Beyond Your Finance — Marketing Automation")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

orchestrator = Orchestrator()


@app.on_event("startup")
def _startup() -> None:
    init_db()


def _ctx(request: Request, **extra) -> dict:
    ctx = {
        "request": request,
        "brand": load_brand(),
        "llm_enabled": get_llm().enabled,
        "ItemStatus": ItemStatus,
    }
    ctx.update(extra)
    return ctx


@app.get("/")
def dashboard(request: Request, session: Session = Depends(get_session)):
    runs = session.scalars(select(PipelineRun).order_by(PipelineRun.created_at.desc())).all()
    pending = session.scalars(
        select(ContentItem).where(ContentItem.status == ItemStatus.PENDING_REVIEW)
    ).all()
    approved = session.scalars(
        select(ContentItem).where(ContentItem.status == ItemStatus.APPROVED)
    ).all()
    published = session.scalars(
        select(ContentItem).where(ContentItem.status == ItemStatus.PUBLISHED)
    ).all()
    return templates.TemplateResponse(
        "dashboard.html",
        _ctx(
            request,
            runs=runs,
            pending=pending,
            approved=approved,
            published_count=len(published),
        ),
    )


@app.post("/runs")
def start_run(topic: str = Form(default="")):
    run_id = orchestrator.run_cycle(topic=topic.strip() or None)
    return RedirectResponse(url=f"/runs/{run_id}", status_code=303)


@app.get("/runs/{run_id}")
def run_detail(run_id: int, request: Request, session: Session = Depends(get_session)):
    run = session.get(PipelineRun, run_id)
    if not run:
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse("run.html", _ctx(request, run=run))


@app.get("/items/{item_id}")
def item_detail(item_id: int, request: Request, session: Session = Depends(get_session)):
    item = session.get(ContentItem, item_id)
    if not item:
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse("item.html", _ctx(request, item=item))


@app.post("/items/{item_id}/approve")
def approve_item(item_id: int, note: str = Form(default="")):
    orchestrator.approve(item_id, note.strip() or None)
    return RedirectResponse(url=f"/items/{item_id}", status_code=303)


@app.post("/items/{item_id}/reject")
def reject_item(item_id: int, note: str = Form(default="")):
    orchestrator.reject(item_id, note.strip() or None)
    return RedirectResponse(url=f"/items/{item_id}", status_code=303)


@app.post("/items/{item_id}/publish")
def publish_item(item_id: int):
    orchestrator.publish_item(item_id)
    return RedirectResponse(url=f"/items/{item_id}", status_code=303)


@app.post("/runs/{run_id}/analytics")
def run_analytics(run_id: int, request: Request, session: Session = Depends(get_session)):
    insight = orchestrator.collect_analytics(run_id)
    run = session.get(PipelineRun, run_id)
    return templates.TemplateResponse(
        "analytics.html", _ctx(request, run=run, insight=insight)
    )
