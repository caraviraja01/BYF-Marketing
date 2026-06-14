"""Pipeline orchestrator.

Runs the agent chain and persists every stage to the database. The chain stops at
the human-review gate: items land as PENDING_REVIEW (or NEEDS_REVISION) and nothing
is published until a human approves it in the dashboard / CLI.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

from .agents import (
    AnalyticsAgent,
    CreativeAgent,
    ResearchAgent,
    ScriptAgent,
    StrategyAgent,
    VerificationAgent,
)
from .db import session_scope
from .integrations.analytics_providers import AnalyticsProvider
from .integrations.social import get_publisher
from .integrations.web_research import WebResearchConnector
from .models import ContentItem, ItemStatus, PipelineRun, RunStatus
from .schemas import AnalyticsInsight, ContentIdea, ContentStrategy, ResearchBrief, Script

log = logging.getLogger("byf.orchestrator")


def _simulate_publish() -> bool:
    """In dev we simulate publishing (clearly labelled) so the full loop is demoable."""
    return os.getenv("BYF_SIMULATE_PUBLISH", "true").lower() in {"1", "true", "yes"}


@dataclass
class Orchestrator:
    research: ResearchAgent = None  # type: ignore[assignment]
    strategy: StrategyAgent = None  # type: ignore[assignment]
    script: ScriptAgent = None  # type: ignore[assignment]
    creative: CreativeAgent = None  # type: ignore[assignment]
    verify: VerificationAgent = None  # type: ignore[assignment]
    analytics: AnalyticsAgent = None  # type: ignore[assignment]
    web: WebResearchConnector = None  # type: ignore[assignment]
    metrics_provider: AnalyticsProvider = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self.research = self.research or ResearchAgent()
        self.strategy = self.strategy or StrategyAgent()
        self.script = self.script or ScriptAgent()
        self.creative = self.creative or CreativeAgent()
        self.verify = self.verify or VerificationAgent()
        self.analytics = self.analytics or AnalyticsAgent()
        self.web = self.web or WebResearchConnector()
        self.metrics_provider = self.metrics_provider or AnalyticsProvider()

    # ── Stages 1–5: research → strategy → produce → verify ─────────────────────
    def create_run(self, *, topic: str | None = None) -> int:
        """Create the run row immediately and return its id (for background execution)."""
        with session_scope() as session:
            run = PipelineRun(topic=topic, status=RunStatus.RESEARCHING)
            session.add(run)
            session.flush()
            return run.id

    def execute_run(self, run_id: int, *, items_per_run: int = 4, raise_on_error: bool = False) -> None:
        """Run the heavy pipeline for an existing run, up to the human-review gate.

        Safe to call from a background task: failures are recorded on the run
        (status=FAILED, error set) rather than raised, unless ``raise_on_error``.
        """
        with session_scope() as session:
            run = session.get(PipelineRun, run_id)
            if run is None:
                raise ValueError(f"Run {run_id} not found")
            try:
                log.info("Run %s: research", run_id)
                signals = self.web.fetch_signals(run.topic)
                brief: ResearchBrief = self.research.run(topic=run.topic, web_signals=signals)
                run.research = brief.model_dump()
                run.status = RunStatus.STRATEGISING

                log.info("Run %s: strategy", run_id)
                strategy: ContentStrategy = self.strategy.run(
                    research=brief, items_per_run=items_per_run
                )
                run.strategy = strategy.model_dump()
                run.status = RunStatus.PRODUCING
                session.flush()

                for idea in strategy.ideas:
                    self._produce_item(session, run_id, idea)

                run.status = RunStatus.AWAITING_REVIEW
                log.info("Run %s: awaiting human review", run_id)
            except Exception as exc:
                log.exception("Run %s failed", run_id)
                run.status = RunStatus.FAILED
                run.error = str(exc)
                if raise_on_error:
                    raise

    def run_cycle(self, *, topic: str | None = None, items_per_run: int = 4) -> int:
        """Synchronous create + execute (used by the CLI and tests). Returns the run id."""
        run_id = self.create_run(topic=topic)
        self.execute_run(run_id, items_per_run=items_per_run, raise_on_error=True)
        return run_id

    def _produce_item(self, session: Any, run_id: int, idea: ContentIdea) -> None:
        script: Script = self.script.run(idea=idea)
        creative = self.creative.run(script=script)
        verification = self.verify.run(script=script, creative=creative.model_dump())

        status = ItemStatus.PENDING_REVIEW if verification.passed else ItemStatus.NEEDS_REVISION
        item = ContentItem(
            run_id=run_id,
            platform=idea.platform,
            title=idea.title,
            pillar=idea.pillar,
            status=status,
            idea=idea.model_dump(),
            script=script.model_dump(),
            creative=creative.model_dump(),
            verification=verification.model_dump(),
        )
        session.add(item)

    # ── Human gate ─────────────────────────────────────────────────────────────
    def approve(self, item_id: int, note: str | None = None) -> None:
        self._set_status(item_id, ItemStatus.APPROVED, note)

    def reject(self, item_id: int, note: str | None = None) -> None:
        self._set_status(item_id, ItemStatus.REJECTED, note)

    def _set_status(self, item_id: int, status: ItemStatus, note: str | None) -> None:
        with session_scope() as session:
            item = session.get(ContentItem, item_id)
            if not item:
                raise ValueError(f"Content item {item_id} not found")
            item.status = status
            if note:
                item.review_note = note

    # ── Stage: publish (approved items only) ───────────────────────────────────
    def publish_item(self, item_id: int) -> str:
        with session_scope() as session:
            item = session.get(ContentItem, item_id)
            if not item:
                raise ValueError(f"Content item {item_id} not found")
            if item.status != ItemStatus.APPROVED:
                raise ValueError("Only APPROVED items can be published.")

            publisher = get_publisher(item.platform)
            result = publisher.publish(script=item.script or {}, creative=item.creative or {})

            if not result.success:
                if _simulate_publish():
                    # Clearly-labelled simulation so the loop is demoable without keys.
                    item.published_ref = f"simulated://{item.platform}/{item.id}"
                    item.status = ItemStatus.PUBLISHED
                    return item.published_ref
                raise RuntimeError(result.detail)

            item.published_ref = result.ref
            item.status = ItemStatus.PUBLISHED
            return result.ref or ""

    # ── Stage 6: analytics feedback ────────────────────────────────────────────
    def collect_analytics(self, run_id: int) -> AnalyticsInsight:
        with session_scope() as session:
            run = session.get(PipelineRun, run_id)
            if not run:
                raise ValueError(f"Run {run_id} not found")
            published = [i for i in run.items if i.status == ItemStatus.PUBLISHED]
            metrics: list[dict[str, Any]] = []
            for item in published:
                m = self.metrics_provider.metrics_dict(
                    platform=item.platform,
                    published_ref=item.published_ref or "",
                    seed=item.id,
                )
                item.analytics = m
                metrics.append(m)

            if not metrics:
                raise ValueError("No published items to analyse yet.")

            insight = self.analytics.run(metrics=metrics)
            run.status = RunStatus.COMPLETED
            return insight
