"""YourChartered.AI — public AI Q&A + "Connect an Expert" live chat routes."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    Form,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from .accounts import (
    authenticate,
    create_user,
    current_user,
    get_user_by_email,
    home_path_for,
)
from .assistant import answer_question, title_for
from .brand import load_brand
from .db import SessionLocal, get_session
from .llm import get_llm
from .models import (
    AskConversation,
    AskMessage,
    ChatMessage,
    ChatStatus,
    ExpertChat,
    User,
    UserRole,
)
from .realtime import LOBBY, chat_room, manager

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

router = APIRouter()


def _ctx(request: Request, user: User | None, **extra) -> dict:
    ctx = {
        "request": request,
        "brand": load_brand(),
        "user": user,
        "llm_enabled": get_llm().enabled,
        "now": datetime.now(timezone.utc),
    }
    ctx.update(extra)
    return ctx


# ── Auth ──────────────────────────────────────────────────────────────────────
@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, user: User | None = Depends(current_user)):
    if user:
        return RedirectResponse(home_path_for(user), status_code=303)
    return templates.TemplateResponse(
        "ask/login.html", _ctx(request, None, error=None)
    )


@router.post("/login")
def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    session: Session = Depends(get_session),
):
    user = authenticate(session, email, password)
    if not user:
        return templates.TemplateResponse(
            "ask/login.html",
            _ctx(request, None, error="Wrong email or password."),
            status_code=401,
        )
    request.session["user_id"] = user.id
    request.session["role"] = user.role.value
    return RedirectResponse(home_path_for(user), status_code=303)


@router.get("/signup", response_class=HTMLResponse)
def signup_page(request: Request, user: User | None = Depends(current_user)):
    if user:
        return RedirectResponse(home_path_for(user), status_code=303)
    return templates.TemplateResponse(
        "ask/signup.html", _ctx(request, None, error=None)
    )


@router.post("/signup")
def signup_submit(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    session: Session = Depends(get_session),
):
    if len(password) < 6:
        return templates.TemplateResponse(
            "ask/signup.html",
            _ctx(request, None, error="Use a password of at least 6 characters."),
            status_code=400,
        )
    if get_user_by_email(session, email):
        return templates.TemplateResponse(
            "ask/signup.html",
            _ctx(request, None, error="That email already has an account — try logging in."),
            status_code=400,
        )
    user = create_user(session, email=email, name=name, password=password, role=UserRole.USER)
    request.session["user_id"] = user.id
    request.session["role"] = user.role.value
    return RedirectResponse("/ask", status_code=303)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


# ── AI Q&A ──────────────────────────────────────────────────────────────────
def _require_user(request: Request, session: Session) -> User | None:
    uid = request.session.get("user_id")
    return session.get(User, uid) if uid else None


@router.get("/ask", response_class=HTMLResponse)
@router.get("/ask/{conversation_id}", response_class=HTMLResponse)
def ask_page(
    request: Request,
    conversation_id: int | None = None,
    session: Session = Depends(get_session),
):
    user = _require_user(request, session)
    if not user:
        return RedirectResponse("/login", status_code=303)

    conversations = session.scalars(
        select(AskConversation)
        .where(AskConversation.user_id == user.id)
        .order_by(AskConversation.updated_at.desc())
    ).all()

    active = None
    if conversation_id is not None:
        active = session.get(AskConversation, conversation_id)
        if not active or active.user_id != user.id:
            return RedirectResponse("/ask", status_code=303)
    elif conversations:
        active = conversations[0]

    return templates.TemplateResponse(
        "ask/chat.html",
        _ctx(request, user, conversations=conversations, active=active),
    )


@router.post("/ask/new")
def ask_new(request: Request, session: Session = Depends(get_session)):
    user = _require_user(request, session)
    if not user:
        return RedirectResponse("/login", status_code=303)
    convo = AskConversation(user_id=user.id, title="New question")
    session.add(convo)
    session.commit()
    return RedirectResponse(f"/ask/{convo.id}", status_code=303)


@router.post("/ask/message")
def ask_message(
    request: Request,
    question: str = Form(...),
    conversation_id: int | None = Form(default=None),
    session: Session = Depends(get_session),
):
    """Persist the question, generate an AI answer, return both as JSON.

    Creates a fresh conversation when no (valid) ``conversation_id`` is given, so the
    first question on a blank page just works.
    """
    user = _require_user(request, session)
    if not user:
        return JSONResponse({"error": "not_authenticated"}, status_code=401)

    convo = session.get(AskConversation, conversation_id) if conversation_id else None
    if convo and convo.user_id != user.id:
        return JSONResponse({"error": "not_found"}, status_code=404)
    if convo is None:
        convo = AskConversation(user_id=user.id, title="New question")
        session.add(convo)
        session.flush()

    question = question.strip()
    if not question:
        return JSONResponse({"error": "empty"}, status_code=400)

    history = [{"role": m.role, "content": m.content} for m in convo.messages]
    session.add(AskMessage(conversation_id=convo.id, role="user", content=question))
    if convo.title == "New question" or not convo.messages:
        convo.title = title_for(question)

    answer = answer_question(question, history)
    answer_msg = AskMessage(conversation_id=convo.id, role="assistant", content=answer)
    session.add(answer_msg)
    convo.updated_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(answer_msg)

    return JSONResponse(
        {
            "answer": answer,
            "message_id": answer_msg.id,
            "conversation_id": convo.id,
            "title": convo.title,
        }
    )


@router.post("/ask/connect")
def ask_connect(
    request: Request,
    conversation_id: int = Form(...),
    message_id: int = Form(default=0),
    session: Session = Depends(get_session),
):
    """Create a live expert chat seeded with the AI exchange and notify experts."""
    user = _require_user(request, session)
    if not user:
        return RedirectResponse("/login", status_code=303)
    convo = session.get(AskConversation, conversation_id)
    if not convo or convo.user_id != user.id:
        return RedirectResponse("/ask", status_code=303)

    seed_answer = session.get(AskMessage, message_id) if message_id else None
    # The user message just before this answer is the seed question.
    seed_question = None
    msgs = convo.messages
    if seed_answer:
        for i, m in enumerate(msgs):
            if m.id == seed_answer.id:
                for prev in reversed(msgs[:i]):
                    if prev.role == "user":
                        seed_question = prev.content
                        break
                break
    if seed_question is None:
        for m in reversed(msgs):
            if m.role == "user":
                seed_question = m.content
                break

    chat = ExpertChat(
        requester_id=user.id,
        subject=convo.title,
        seed_question=seed_question,
        seed_answer=seed_answer.content if seed_answer else None,
        status=ChatStatus.WAITING,
    )
    session.add(chat)
    session.commit()
    session.refresh(chat)

    _notify_lobby(
        {
            "type": "new_request",
            "chat_id": chat.id,
            "subject": chat.subject,
            "requester": user.name,
        }
    )
    return RedirectResponse(f"/chat/{chat.id}", status_code=303)


# ── Expert inbox ───────────────────────────────────────────────────────────────
@router.get("/expert", response_class=HTMLResponse)
def expert_inbox(request: Request, session: Session = Depends(get_session)):
    user = _require_user(request, session)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if not user.is_expert:
        return RedirectResponse("/ask", status_code=303)

    waiting, mine = _expert_queues(session, user)
    return templates.TemplateResponse(
        "ask/expert_inbox.html",
        _ctx(request, user, waiting=waiting, mine=mine),
    )


@router.get("/expert/inbox.json")
def expert_inbox_json(request: Request, session: Session = Depends(get_session)):
    user = _require_user(request, session)
    if not user or not user.is_expert:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    waiting, mine = _expert_queues(session, user)

    def row(c: ExpertChat) -> dict:
        return {
            "id": c.id,
            "subject": c.subject,
            "requester": c.requester.name if c.requester else "User",
            "status": c.status.value,
            "messages": len(c.messages),
        }

    return JSONResponse({"waiting": [row(c) for c in waiting], "mine": [row(c) for c in mine]})


def _expert_queues(session: Session, user: User) -> tuple[list[ExpertChat], list[ExpertChat]]:
    waiting = session.scalars(
        select(ExpertChat)
        .where(ExpertChat.status == ChatStatus.WAITING)
        .order_by(ExpertChat.created_at.asc())
    ).all()
    mine = session.scalars(
        select(ExpertChat)
        .where(ExpertChat.expert_id == user.id, ExpertChat.status == ChatStatus.ACTIVE)
        .order_by(ExpertChat.updated_at.desc())
    ).all()
    return waiting, mine


@router.post("/expert/claim/{chat_id}")
def expert_claim(request: Request, chat_id: int, session: Session = Depends(get_session)):
    user = _require_user(request, session)
    if not user or not user.is_expert:
        return RedirectResponse("/login", status_code=303)
    chat = session.get(ExpertChat, chat_id)
    if not chat:
        return RedirectResponse("/expert", status_code=303)
    if chat.status == ChatStatus.WAITING:
        chat.expert_id = user.id
        chat.status = ChatStatus.ACTIVE
        session.commit()
        _notify_lobby({"type": "claimed", "chat_id": chat.id})
    return RedirectResponse(f"/chat/{chat.id}", status_code=303)


# ── Live chat room ─────────────────────────────────────────────────────────────
def _can_view(chat: ExpertChat, user: User) -> bool:
    if user.id == chat.requester_id:
        return True
    if user.is_expert and (chat.expert_id == user.id or chat.status == ChatStatus.WAITING):
        return True
    return False


@router.get("/chat/{chat_id}", response_class=HTMLResponse)
def chat_room_page(request: Request, chat_id: int, session: Session = Depends(get_session)):
    user = _require_user(request, session)
    if not user:
        return RedirectResponse("/login", status_code=303)
    chat = session.get(ExpertChat, chat_id)
    if not chat or not _can_view(chat, user):
        return RedirectResponse(home_path_for(user), status_code=303)

    other = chat.expert if user.id == chat.requester_id else chat.requester
    return templates.TemplateResponse(
        "ask/room.html",
        _ctx(request, user, chat=chat, other=other),
    )


@router.post("/chat/{chat_id}/close")
def chat_close(request: Request, chat_id: int, session: Session = Depends(get_session)):
    user = _require_user(request, session)
    if not user:
        return RedirectResponse("/login", status_code=303)
    chat = session.get(ExpertChat, chat_id)
    if chat and _can_view(chat, user):
        chat.status = ChatStatus.CLOSED
        chat.closed_at = datetime.now(timezone.utc)
        session.commit()
    return RedirectResponse(home_path_for(user), status_code=303)


@router.websocket("/ws/chat/{chat_id}")
async def chat_ws(websocket: WebSocket, chat_id: int):
    uid = websocket.session.get("user_id") if "session" in websocket.scope else None
    if not uid:
        await websocket.close(code=4401)
        return

    # Authorise against the DB up front.
    with SessionLocal() as session:
        chat = session.get(ExpertChat, chat_id)
        user = session.get(User, uid)
        if not chat or not user or not _can_view(chat, user):
            await websocket.close(code=4403)
            return
        sender_name = user.name

    room = chat_room(chat_id)
    await manager.connect(room, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            body = (data or {}).get("body", "").strip()
            if not body:
                continue
            with SessionLocal() as session:
                chat = session.get(ExpertChat, chat_id)
                if not chat or chat.status == ChatStatus.CLOSED:
                    continue
                msg = ChatMessage(chat_id=chat_id, sender_id=uid, body=body)
                session.add(msg)
                # First reply from a waiting chat activates it.
                if chat.status == ChatStatus.WAITING:
                    chat.status = ChatStatus.ACTIVE
                chat.updated_at = datetime.now(timezone.utc)
                session.commit()
                session.refresh(msg)
                created = msg.created_at
            await manager.broadcast(
                room,
                {
                    "type": "message",
                    "sender_id": uid,
                    "sender_name": sender_name,
                    "body": body,
                    "at": created.strftime("%H:%M"),
                },
            )
    except WebSocketDisconnect:
        await manager.disconnect(room, websocket)
    except Exception:
        await manager.disconnect(room, websocket)


def _notify_lobby(payload: dict) -> None:
    """Fire-and-forget broadcast to online experts (safe outside an event loop)."""
    import asyncio

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(manager.broadcast(LOBBY, payload))
    except RuntimeError:
        pass  # no running loop (e.g. sync test context) — inbox poll will catch up


@router.websocket("/ws/lobby")
async def lobby_ws(websocket: WebSocket):
    uid = websocket.session.get("user_id") if "session" in websocket.scope else None
    if not uid:
        await websocket.close(code=4401)
        return
    with SessionLocal() as session:
        user = session.get(User, uid)
        if not user or not user.is_expert:
            await websocket.close(code=4403)
            return
    await manager.connect(LOBBY, websocket)
    try:
        while True:
            await websocket.receive_text()  # keep-alive; experts only listen
    except WebSocketDisconnect:
        await manager.disconnect(LOBBY, websocket)
    except Exception:
        await manager.disconnect(LOBBY, websocket)
