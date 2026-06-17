"""First-run account bootstrap.

Ensures there's always a way in: an admin (from BYF_AUTH_USERNAME / BYF_AUTH_PASSWORD
when set), and — in non-production / mock mode — a demo expert and user so the whole
YourChartered.AI flow is testable out of the box.
"""
from __future__ import annotations

import logging

from sqlalchemy import select

from .accounts import create_user, get_user_by_email
from .db import SessionLocal
from .models import User, UserRole
from .settings import get_settings

log = logging.getLogger("byf.bootstrap")


def _admin_email(username: str) -> str:
    return username if "@" in username else f"{username}@beyondyourfinance.app"


def ensure_seed_accounts() -> None:
    settings = get_settings()
    with SessionLocal() as session:
        has_admin = session.scalar(select(User).where(User.role == UserRole.ADMIN)) is not None

        # Promote the configured dashboard credentials into a real admin account.
        if settings.byf_auth_password and not has_admin:
            email = _admin_email(settings.byf_auth_username)
            if not get_user_by_email(session, email):
                create_user(
                    session,
                    email=email,
                    name="BYF Admin",
                    password=settings.byf_auth_password,
                    role=UserRole.ADMIN,
                    headline="Beyond Your Finance",
                )
                log.info("Seeded admin account %s", email)
                has_admin = True

        # In dev / mock mode, seed friendly demo logins so the product is clickable.
        if settings.byf_env != "production":
            if not has_admin:
                _ensure(session, "admin@byf.test", "BYF Admin", "admin123",
                        UserRole.ADMIN, "Beyond Your Finance")
            _ensure(session, "expert@byf.test", "CA Priya Sharma", "expert123",
                    UserRole.EXPERT, "Chartered Accountant · Tax & Startup Finance")
            _ensure(session, "user@byf.test", "Demo User", "user123", UserRole.USER, None)


def _ensure(session, email, name, password, role, headline) -> None:
    if not get_user_by_email(session, email):
        create_user(session, email=email, name=name, password=password, role=role, headline=headline)
        log.info("Seeded %s account %s", role.value, email)
