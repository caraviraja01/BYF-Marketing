"""HTTP/WebSocket tests for the YourChartered.AI Q&A + expert-chat product.

Runs in mock mode (no API key) against a throwaway SQLite DB, exercising the full
flow: signup → ask → connect expert → claim → live WebSocket chat.
"""
from __future__ import annotations

import os
import tempfile

import pytest

_TMP = tempfile.mkdtemp()
os.environ["BYF_DB_URL"] = f"sqlite:///{_TMP}/yc_test.db"
os.environ["ANTHROPIC_API_KEY"] = ""        # force mock answers
os.environ["BYF_SECRET_KEY"] = "test-secret"  # stable session signing
os.environ["BYF_ENV"] = "development"        # seeds demo expert/user

from starlette.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture()
def client():
    with TestClient(app) as c:  # context triggers startup (db init + seed accounts)
        yield c


def test_login_required_for_ask(client):
    r = client.get("/ask", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/login"


def test_signup_ask_and_get_disclaimer(client):
    r = client.post(
        "/signup",
        data={"name": "Asha", "email": "asha@example.com", "password": "secret1"},
        follow_redirects=False,
    )
    assert r.status_code == 303 and r.headers["location"] == "/ask"

    r = client.post("/ask/message", data={"question": "How does GST input credit work?"})
    assert r.status_code == 200
    data = r.json()
    # Every answer must carry the educational disclaimer.
    assert "informational purposes only" in data["answer"].lower()
    assert data["conversation_id"] and data["message_id"]


def test_connect_expert_claim_and_live_chat(client):
    client.post(
        "/signup",
        data={"name": "Ravi", "email": "ravi@example.com", "password": "secret1"},
    )
    ans = client.post("/ask/message", data={"question": "Do I need to deduct TDS?"}).json()
    r = client.post(
        "/ask/connect",
        data={"conversation_id": ans["conversation_id"], "message_id": ans["message_id"]},
        follow_redirects=False,
    )
    assert r.status_code == 303
    chat_id = int(r.headers["location"].split("/chat/")[1])

    # Expert claims the waiting request.
    expert = TestClient(app)
    er = expert.post(
        "/login", data={"email": "expert@byf.test", "password": "expert123"},
        follow_redirects=False,
    )
    assert er.headers["location"] == "/expert"
    inbox = expert.get("/expert/inbox.json").json()
    assert any(w["id"] == chat_id for w in inbox["waiting"])
    expert.post(f"/expert/claim/{chat_id}", follow_redirects=False)

    # Messages flow both ways over the WebSocket and persist.
    with expert.websocket_connect(f"/ws/chat/{chat_id}") as ews, \
            client.websocket_connect(f"/ws/chat/{chat_id}") as uws:
        ews.send_json({"type": "message", "body": "Hi, CA here."})
        assert uws.receive_json()["body"] == "Hi, CA here."
        ews.receive_json()  # drain the echo to the sender's own socket
        uws.send_json({"type": "message", "body": "Thanks!"})
        assert ews.receive_json()["body"] == "Thanks!"

    page = client.get(f"/chat/{chat_id}")
    assert page.status_code == 200 and "Thanks!" in page.text


def test_non_expert_cannot_open_inbox(client):
    client.post("/signup", data={"name": "Z", "email": "z@example.com", "password": "secret1"})
    r = client.get("/expert", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/ask"


def test_admin_dashboard_is_gated(client):
    # A regular user is bounced off the firm-internal marketing dashboard.
    client.post("/signup", data={"name": "Q", "email": "q@example.com", "password": "secret1"})
    r = client.get("/dashboard", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/ask"
