"""User accounts & password auth for YourChartered.AI.

Stdlib-only password hashing (PBKDF2) so we add no dependency. Sessions store the
user id; role decides where each person lands after login.
"""
from __future__ import annotations

import hashlib
import hmac
import os
from typing import Iterator

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_session
from .models import User, UserRole

_ITERATIONS = 240_000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS)
    return f"pbkdf2_sha256${_ITERATIONS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters, salt_hex, hash_hex = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(iters)
        )
        return hmac.compare_digest(dk.hex(), hash_hex)
    except (ValueError, AttributeError):
        return False


def create_user(
    session: Session,
    *,
    email: str,
    name: str,
    password: str,
    role: UserRole = UserRole.USER,
    headline: str | None = None,
) -> User:
    user = User(
        email=email.strip().lower(),
        name=name.strip() or email.split("@")[0],
        password_hash=hash_password(password),
        role=role,
        headline=headline,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def get_user_by_email(session: Session, email: str) -> User | None:
    return session.scalar(select(User).where(User.email == email.strip().lower()))


def authenticate(session: Session, email: str, password: str) -> User | None:
    user = get_user_by_email(session, email)
    if user and verify_password(password, user.password_hash):
        return user
    return None


# ── FastAPI dependencies ──────────────────────────────────────────────────────
def current_user(
    request: Request, session: Session = Depends(get_session)
) -> User | None:
    """Resolve the logged-in user from the session cookie (or None)."""
    uid = request.session.get("user_id")
    return session.get(User, uid) if uid else None


def home_path_for(user: User) -> str:
    """Where a user lands after login, by role."""
    if user.role == UserRole.ADMIN:
        return "/dashboard"
    if user.role == UserRole.EXPERT:
        return "/expert"
    return "/ask"


def session_dep() -> Iterator[Session]:  # convenience re-export for routers
    yield from get_session()
