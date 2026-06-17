"""FastAPI app: the dashboard, the human-review gate, and the analytics view."""
from __future__ import annotations

import hmac
import secrets
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

from .ask_routes import router as ask_router
from .brand import load_brand
from .bootstrap import ensure_seed_accounts
from .db import SessionLocal, get_session, init_db, reset_db
from .llm import get_llm
from .models import ContentItem, ItemStatus, PipelineRun
from .orchestrator import Orchestrator
from .settings import get_settings

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
settings = get_settings()

app = FastAPI(title="YourChartered.AI — Beyond Your Finance")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Paths reachable without logging in (the cron task is token-protected instead).
_PUBLIC_PREFIXES = ("/login", "/signup", "/static", "/health", "/favicon", "/tasks/")
# The marketing dashboard is firm-internal: admins only.
_ADMIN_PREFIXES = ("/dashboard", "/runs", "/items")


@app.middleware("http")
async def require_login(request: Request, call_next):
    path = request.url.path
    if not path.startswith(_PUBLIC_PREFIXES):
        if not request.session.get("user_id"):
            return RedirectResponse(url="/login", status_code=303)
        # Keep the marketing dashboard restricted to admins.
        if path.startswith(_ADMIN_PREFIXES) and request.session.get("role") != "admin":
            role = request.session.get("role")
            return RedirectResponse(url="/expert" if role == "expert" else "/ask", status_code=303)
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
app.include_router(ask_router)


@app.on_event("startup")
def _startup() -> None:
    init_db()
    ensure_seed_accounts()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.api_route("/tasks/prepare-daily", methods=["GET", "POST"])
def prepare_daily(background_tasks: BackgroundTasks, token: str = ""):
    """Cron target: prepare today's scheduled content across all runs.

    Protected by BYF_CRON_TOKEN (point Render Cron / an external cron here).
    Marks due items now and prepares them in the background.
    """
    expected = settings.byf_cron_token
    if not expected or not hmac.compare_digest(token, expected):
        return JSONResponse({"error": "invalid or missing token"}, status_code=403)
    ids = orchestrator.mark_preparing(mode="due")
    background_tasks.add_task(orchestrator.prepare_marked, ids)
    return {"scheduled_for_preparation": len(ids)}


@app.api_route("/tasks/reset-db", methods=["GET", "POST"])
def reset_database(token: str = "", confirm: str = ""):
    """Drop & recreate all tables (token-protected). One-time schema fix; clears data."""
    expected = settings.byf_cron_token
    if not expected or not hmac.compare_digest(token, expected):
        return JSONResponse({"error": "invalid or missing token"}, status_code=403)
    if confirm != "yes":
        return JSONResponse({"error": "add &confirm=yes to confirm — this clears all data"}, status_code=400)
    reset_db()
    return {"status": "database reset"}


@app.get("/")
def root(request: Request):
    """Send each visitor to their home: admins to the dashboard, everyone else to the AI."""
    role = request.session.get("role")
    if role == "admin":
        return RedirectResponse(url="/dashboard", status_code=303)
    if role == "expert":
        return RedirectResponse(url="/expert", status_code=303)
    return RedirectResponse(url="/ask", status_code=303)


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
        "flash": request.session.pop("flash", None) if "session" in request.scope else None,
    }
    ctx.update(extra)
    return ctx


@app.get("/dashboard")
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


def _flash(request: Request, text: str, kind: str = "ok") -> None:
    request.session["flash"] = {"text": text, "kind": kind}


# ── AI refine routes (errors surfaced as a flash, never a 500) ─────────────────
@app.post("/runs/{run_id}/refine-research")
def refine_research(request: Request, run_id: int, feedback: str = Form(...)):
    try:
        orchestrator.refine_research(run_id, feedback)
        _flash(request, "Research updated with your changes.")
    except Exception as exc:
        _flash(request, f"Couldn't apply that change: {exc}. Try rephrasing.", "warn")
    return RedirectResponse(url=f"/runs/{run_id}#research", status_code=303)


@app.post("/runs/{run_id}/refine-strategy")
def refine_strategy(request: Request, run_id: int, feedback: str = Form(...)):
    try:
        orchestrator.refine_strategy(run_id, feedback)
        _flash(request, "Strategy & calendar updated with your changes.")
    except Exception as exc:
        _flash(request, f"Couldn't apply that change: {exc}. Try rephrasing.", "warn")
    return RedirectResponse(url=f"/runs/{run_id}#strategy", status_code=303)


@app.post("/items/{item_id}/refine-script")
def refine_script(request: Request, item_id: int, feedback: str = Form(...)):
    try:
        orchestrator.refine_script(item_id, feedback)
        _flash(request, "Added a revised script option (selected).")
    except Exception as exc:
        _flash(request, f"Couldn't revise the script: {exc}. Try rephrasing.", "warn")
    return RedirectResponse(url=f"/items/{item_id}#script", status_code=303)


@app.post("/items/{item_id}/refine-creative")
def refine_creative(request: Request, item_id: int, feedback: str = Form(...)):
    try:
        orchestrator.refine_creative(item_id, feedback)
        _flash(request, "Added a revised creative concept (selected). Click Generate to render it.")
    except Exception as exc:
        _flash(request, f"Couldn't revise the creative: {exc}. Try rephrasing.", "warn")
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
def generate_creative(request: Request, item_id: int, background_tasks: BackgroundTasks):
    # Higgsfield image/video jobs take minutes — mark generating now and run in the
    # background so the request returns immediately (the page auto-refreshes).
    orchestrator.mark_creative_generating(item_id)
    background_tasks.add_task(orchestrator.realize_creative, item_id)
    _flash(request, "Generating your creative with Higgsfield… this can take a few minutes.")
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


@app.post("/runs/{run_id}/prepare-next")
def prepare_next(request: Request, run_id: int, background_tasks: BackgroundTasks):
    # Preparing runs the agents (minutes in live mode) — mark + run in background so
    # the request returns immediately; the page auto-refreshes while items prepare.
    ids = orchestrator.mark_preparing(run_id=run_id, mode="next")
    if ids:
        background_tasks.add_task(orchestrator.prepare_marked, ids)
        _flash(request, f"Preparing {len(ids)} item(s)… this takes a few minutes. The page refreshes automatically.")
    else:
        _flash(request, "Nothing left to prepare for this cycle.", "warn")
    return RedirectResponse(url=f"/runs/{run_id}#content", status_code=303)


@app.post("/runs/{run_id}/analytics")
def run_analytics(run_id: int, request: Request, session: Session = Depends(get_session)):
    insight = orchestrator.collect_analytics(run_id)
    run = session.get(PipelineRun, run_id)
    return templates.TemplateResponse(
        "analytics.html", _ctx(request, run=run, insight=insight)
    )
