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
from .schemas import (
    AnalyticsInsight,
    ContentIdea,
    ContentStrategy,
    CreativeAsset,
    CreativeSet,
    ResearchBrief,
    Script,
    ScriptSet,
    VerificationResult,
)

log = logging.getLogger("byf.orchestrator")


def _simulate_publish() -> bool:
    """In dev we simulate publishing (clearly labelled) so the full loop is demoable."""
    return os.getenv("BYF_SIMULATE_PUBLISH", "true").lower() in {"1", "true", "yes"}


def _fallback_on_error() -> bool:
    """When a live agent call fails, fall back to its draft output and warn instead
    of failing the whole run. Keeps the dashboard populated; set false to surface
    raw errors instead."""
    return os.getenv("BYF_FALLBACK_TO_MOCK_ON_ERROR", "true").lower() in {"1", "true", "yes"}


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
        warnings: list[str] = []
        with session_scope() as session:
            run = session.get(PipelineRun, run_id)
            if run is None:
                raise ValueError(f"Run {run_id} not found")
            try:
                log.info("Run %s: research", run_id)
                signals = self.web.fetch_signals(run.topic)
                brief: ResearchBrief = self._run_agent(
                    self.research, "research", warnings, raise_on_error,
                    topic=run.topic, web_signals=signals,
                )
                run.research = brief.model_dump()
                run.status = RunStatus.STRATEGISING

                log.info("Run %s: strategy", run_id)
                strategy: ContentStrategy = self._run_agent(
                    self.strategy, "strategy", warnings, raise_on_error,
                    research=brief, items_per_run=items_per_run,
                )
                run.strategy = strategy.model_dump()
                run.status = RunStatus.PRODUCING
                session.flush()

                for idea in strategy.ideas:
                    self._produce_item(session, run_id, idea, warnings, raise_on_error)

                run.warnings = warnings or None
                run.status = RunStatus.AWAITING_REVIEW
                log.info("Run %s: awaiting review (%d warnings)", run_id, len(warnings))
            except Exception as exc:
                log.exception("Run %s failed", run_id)
                run.status = RunStatus.FAILED
                run.error = str(exc)
                run.warnings = warnings or None
                if raise_on_error:
                    raise

    def _run_agent(self, agent: Any, label: str, warnings: list[str], strict: bool, **inputs: Any):
        """Run an agent; on a live failure fall back to its draft output and warn.

        This is what stops a single flaky/over-long Claude response from turning the
        whole run into a dead 'Failed' page.
        """
        try:
            return agent.run(**inputs)
        except Exception as exc:
            log.exception("Agent '%s' failed", label)
            if strict or not _fallback_on_error() or not agent.llm.enabled:
                raise
            warnings.append(
                f"{label}: live generation failed ({type(exc).__name__}: {exc}); "
                "used a draft fallback. Re-run to retry."
            )
            return agent.mock(**inputs)

    def run_cycle(self, *, topic: str | None = None, items_per_run: int = 4) -> int:
        """Synchronous create + execute (used by the CLI and tests). Returns the run id."""
        run_id = self.create_run(topic=topic)
        self.execute_run(run_id, items_per_run=items_per_run, raise_on_error=True)
        return run_id

    def _produce_item(
        self, session: Any, run_id: int, idea: ContentIdea,
        warnings: list[str], strict: bool,
    ) -> None:
        script_set: ScriptSet = self._run_agent(self.script, "script", warnings, strict, idea=idea)
        creative_set: CreativeSet = self._run_agent(
            self.creative, "creative", warnings, strict, script=script_set.variants[0]
        )

        item = ContentItem(
            run_id=run_id,
            platform=idea.platform,
            title=idea.title,
            pillar=idea.pillar,
            status=ItemStatus.PENDING_REVIEW,
            idea=idea.model_dump(),
            scripts=[s.model_dump() for s in script_set.variants],
            selected_script=0,
            creatives=[c.model_dump() for c in creative_set.variants],
            selected_creative=0,
        )
        # Verify the currently-selected script/creative pair.
        verification = self._verify(item, warnings, strict)
        item.verification = verification.model_dump()
        item.status = ItemStatus.PENDING_REVIEW if verification.passed else ItemStatus.NEEDS_REVISION
        session.add(item)

    def _verify(self, item: ContentItem, warnings: list[str], strict: bool) -> VerificationResult:
        return self._run_agent(
            self.verify, "verify", warnings, strict,
            script=item.script or {}, creative=item.creative or {},
        )

    # ── Variant selection (human picks one of the 3) ───────────────────────────
    def select_script(self, item_id: int, index: int) -> None:
        with session_scope() as session:
            item = session.get(ContentItem, item_id)
            if not item:
                raise ValueError(f"Content item {item_id} not found")
            if not (0 <= index < len(item.scripts or [])):
                raise ValueError("Script index out of range")
            item.selected_script = index
            # Re-verify against the newly-chosen script.
            result = self._verify(item, [], strict=False)
            item.verification = result.model_dump()
            if item.status in (ItemStatus.PENDING_REVIEW, ItemStatus.NEEDS_REVISION):
                item.status = (
                    ItemStatus.PENDING_REVIEW if result.passed else ItemStatus.NEEDS_REVISION
                )

    def select_creative(self, item_id: int, index: int) -> None:
        with session_scope() as session:
            item = session.get(ContentItem, item_id)
            if not item:
                raise ValueError(f"Content item {item_id} not found")
            if not (0 <= index < len(item.creatives or [])):
                raise ValueError("Creative index out of range")
            item.selected_creative = index

    def realize_creative(self, item_id: int) -> dict[str, Any]:
        """Generate the actual asset for the selected creative concept (Canva/Higgsfield)."""
        with session_scope() as session:
            item = session.get(ContentItem, item_id)
            if not item or not item.creatives:
                raise ValueError(f"Content item {item_id} has no creative to generate")
            idx = item.selected_creative
            asset = CreativeAsset.model_validate(item.creatives[idx])
            asset = self.creative.realize(asset)
            creatives = list(item.creatives)
            creatives[idx] = asset.model_dump()
            item.creatives = creatives  # reassign so SQLAlchemy detects the change
            return creatives[idx]

    # ── AI refine (apply the user's change requests) ───────────────────────────
    def refine_research(self, run_id: int, feedback: str) -> None:
        with session_scope() as session:
            run = session.get(PipelineRun, run_id)
            if not run or not run.research:
                raise ValueError("No research to refine")
            revised = self.research.refine(previous=run.research, feedback=feedback)
            run.research = revised.model_dump()

    def refine_strategy(self, run_id: int, feedback: str) -> None:
        with session_scope() as session:
            run = session.get(PipelineRun, run_id)
            if not run or not run.strategy:
                raise ValueError("No strategy to refine")
            revised = self.strategy.refine(previous=run.strategy, feedback=feedback)
            run.strategy = revised.model_dump()

    def refine_script(self, item_id: int, feedback: str) -> None:
        """Produce a new script variant from the selected one + feedback, and select it."""
        with session_scope() as session:
            item = session.get(ContentItem, item_id)
            if not item or not item.scripts:
                raise ValueError("No script to refine")
            revised = self.script.refine(
                previous=item.script or {}, feedback=feedback, element_model=Script
            )
            if not (revised.angle or "").startswith("Your edit"):
                revised.angle = f"Your edit · {revised.angle}".strip(" ·")
            scripts = list(item.scripts) + [revised.model_dump()]
            item.scripts = scripts
            item.selected_script = len(scripts) - 1
            result = self._verify(item, [], strict=False)
            item.verification = result.model_dump()
            if item.status in (ItemStatus.PENDING_REVIEW, ItemStatus.NEEDS_REVISION):
                item.status = (
                    ItemStatus.PENDING_REVIEW if result.passed else ItemStatus.NEEDS_REVISION
                )

    def refine_creative(self, item_id: int, feedback: str) -> None:
        """Produce a new creative concept from the selected one + feedback, and select it."""
        with session_scope() as session:
            item = session.get(ContentItem, item_id)
            if not item or not item.creatives:
                raise ValueError("No creative to refine")
            revised = self.creative.refine(
                previous=item.creative or {}, feedback=feedback, element_model=CreativeAsset
            )
            revised.status = "brief_only"  # needs (re)generation after an edit
            revised.asset_url = None
            if not (revised.concept or "").startswith("Your edit"):
                revised.concept = f"Your edit · {revised.concept}".strip(" ·")
            creatives = list(item.creatives) + [revised.model_dump()]
            item.creatives = creatives
            item.selected_creative = len(creatives) - 1

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
