"""ORM models: pipeline runs and the content items that flow through them."""
from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class RunStatus(str, enum.Enum):
    RESEARCHING = "researching"
    STRATEGISING = "strategising"
    PRODUCING = "producing"
    AWAITING_REVIEW = "awaiting_review"
    COMPLETED = "completed"
    FAILED = "failed"


class ItemStatus(str, enum.Enum):
    DRAFT = "draft"                 # script + creative produced
    NEEDS_REVISION = "needs_revision"  # failed verification
    PENDING_REVIEW = "pending_review"  # passed verify, waiting on human
    APPROVED = "approved"           # human approved
    REJECTED = "rejected"           # human rejected
    PUBLISHED = "published"         # live on the platform


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    topic: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[RunStatus] = mapped_column(Enum(RunStatus), default=RunStatus.RESEARCHING)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    # Stage artifacts (structured agent output).
    research: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    strategy: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    items: Mapped[list["ContentItem"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class ContentItem(Base):
    __tablename__ = "content_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("pipeline_runs.id"))
    run: Mapped[PipelineRun] = relationship(back_populates="items")

    platform: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(300))
    pillar: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status: Mapped[ItemStatus] = mapped_column(Enum(ItemStatus), default=ItemStatus.DRAFT)

    idea: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    script: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    creative: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    verification: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    analytics: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)
