"""FastAPI app: the dashboard, the human-review gate, and the analytics view."""
from __future__ import annotations

import hmac
import secrets
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

from .brand import load_brand
from .db import SessionLocal, get_session, init_db
from .llm import get_llm
from .models import ContentItem, ItemStatus, PipelineRun
from .orchestrator import Orchestrator
from .settings import get_settings

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
settings = get_settings()

app = FastAPI(title="Beyond Your Finance — Marketing Automation")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Paths reachable without logging in.
_PUBLIC_PREFIXES = ("/login", "/static", "/health", "/favicon")


@app.middleware("http")
async def require_login(request: Request, call_next):
    if settings.auth_enabled and not request.url.path.startswith(_PUBLIC_PREFIXES):
        if not request.session.get("authed"):
            return RedirectResponse(url="/login", status_code=303)
    return await call_next(request)


# SessionMiddleware is added last so it wraps (runs before) the auth check,
# making request.session available. Secret key signs the session cookie.
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.byf_secret_key or secrets.token_hex(32),
    https_only=settings.byf_env == "production",
    same_site="lax",
)

orchestrator = Orchestrator()


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/login")
def login_form(request: Request):
    if not settings.auth_enabled or request.session.get("authed"):
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(
        "login.html", {"request": request, "brand": load_brand(), "error": None}
    )


@app.post("/login")
def login_submit(request: Request, username: str = Form(default=""), password: str = Form(default="")):
    ok_user = hmac.compare_digest(username.strip(), settings.byf_auth_username)
    ok_pass = hmac.compare_digest(password, settings.byf_auth_password or "")
    if ok_user and ok_pass:
        request.session["authed"] = True
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "brand": load_brand(), "error": "Invalid username or password."},
        status_code=401,
    )


@app.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)


def _ctx(request: Request, **extra) -> dict:
    # Sidebar run history is shown on every page, so query it here (own session).
    with SessionLocal() as session:
        sidebar_runs = session.scalars(
            select(PipelineRun).order_by(PipelineRun.created_at.desc()).limit(30)
        ).all()
    ctx = {
        "request": request,
        "brand": load_brand(),
        "llm_enabled": get_llm().enabled,
        "auth_enabled": settings.auth_enabled,
        "ItemStatus": ItemStatus,
        "sidebar_runs": sidebar_runs,
        "active_run_id": None,
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
def start_run(background_tasks: BackgroundTasks, topic: str = Form(default="")):
    # Create the run immediately, then run the (minutes-long) pipeline in the
    # background so the request returns at once. The run page auto-refreshes.
    run_id = orchestrator.create_run(topic=topic.strip() or None)
    background_tasks.add_task(orchestrator.execute_run, run_id)
    return RedirectResponse(url=f"/runs/{run_id}", status_code=303)


@app.get("/runs/{run_id}")
def run_detail(run_id: int, request: Request, session: Session = Depends(get_session)):
    run = session.get(PipelineRun, run_id)
    if not run:
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse("run.html", _ctx(request, run=run, active_run_id=run_id))


@app.get("/items/{item_id}")
def item_detail(item_id: int, request: Request, session: Session = Depends(get_session)):
    item = session.get(ContentItem, item_id)
    if not item:
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(
        "item.html", _ctx(request, item=item, active_run_id=item.run_id)
    )


# ── AI refine routes ──────────────────────────────────────────────────────────
@app.post("/runs/{run_id}/refine-research")
def refine_research(run_id: int, feedback: str = Form(...)):
    orchestrator.refine_research(run_id, feedback)
    return RedirectResponse(url=f"/runs/{run_id}#research", status_code=303)


@app.post("/runs/{run_id}/refine-strategy")
def refine_strategy(run_id: int, feedback: str = Form(...)):
    orchestrator.refine_strategy(run_id, feedback)
    return RedirectResponse(url=f"/runs/{run_id}#strategy", status_code=303)


@app.post("/items/{item_id}/refine-script")
def refine_script(item_id: int, feedback: str = Form(...)):
    orchestrator.refine_script(item_id, feedback)
    return RedirectResponse(url=f"/items/{item_id}#script", status_code=303)


@app.post("/items/{item_id}/refine-creative")
def refine_creative(item_id: int, feedback: str = Form(...)):
    orchestrator.refine_creative(item_id, feedback)
    return RedirectResponse(url=f"/items/{item_id}#creative", status_code=303)


@app.post("/items/{item_id}/select-script")
def select_script(item_id: int, index: int = Form(...)):
    orchestrator.select_script(item_id, index)
    return RedirectResponse(url=f"/items/{item_id}#script", status_code=303)


@app.post("/items/{item_id}/select-creative")
def select_creative(item_id: int, index: int = Form(...)):
    orchestrator.select_creative(item_id, index)
    return RedirectResponse(url=f"/items/{item_id}#creative", status_code=303)


@app.post("/items/{item_id}/generate-creative")
def generate_creative(item_id: int):
    orchestrator.realize_creative(item_id)
    return RedirectResponse(url=f"/items/{item_id}#creative", status_code=303)


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
