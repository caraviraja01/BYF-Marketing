"""End-to-end tests of the pipeline in mock mode (no API key required)."""
from __future__ import annotations

import os
import tempfile

import pytest

# Point the DB at a throwaway file before app modules read settings.
_TMP = tempfile.mkdtemp()
os.environ["BYF_DB_URL"] = f"sqlite:///{_TMP}/test.db"
os.environ.pop("ANTHROPIC_API_KEY", None)  # force mock mode

from app.agents import (  # noqa: E402
    AnalyticsAgent,
    CreativeAgent,
    ResearchAgent,
    ScriptAgent,
    StrategyAgent,
    VerificationAgent,
)
from app.db import init_db, session_scope  # noqa: E402
from app.models import ContentItem, ItemStatus, RunStatus  # noqa: E402
from app.orchestrator import Orchestrator  # noqa: E402
from app.schemas import ContentIdea, Script  # noqa: E402


@pytest.fixture(autouse=True)
def _db():
    init_db()


def test_agents_run_in_mock_mode():
    brief = ResearchAgent().run(topic="emergency funds")
    assert brief.trending_topics
    strategy = StrategyAgent().run(research=brief)
    assert len(strategy.ideas) >= 1
    idea = strategy.ideas[0]
    script = ScriptAgent().run(idea=idea)
    assert script.hook and script.body
    creative = CreativeAgent().run(script=script)
    assert creative.status in {"brief_only", "generated"}
    verification = VerificationAgent().run(script=script, creative=creative.model_dump())
    assert verification.compliance_ok is True


def test_full_cycle_lands_in_review():
    orch = Orchestrator()
    run_id = orch.run_cycle(topic="index funds explained")
    with session_scope() as session:
        from app.models import PipelineRun

        run = session.get(PipelineRun, run_id)
        assert run.status == RunStatus.AWAITING_REVIEW
        assert run.research and run.strategy
        assert len(run.items) >= 1
        assert all(
            i.status in {ItemStatus.PENDING_REVIEW, ItemStatus.NEEDS_REVISION}
            for i in run.items
        )


def test_approve_publish_and_analytics_loop():
    orch = Orchestrator()
    run_id = orch.run_cycle(topic="compounding basics")
    with session_scope() as session:
        item_ids = [
            i.id
            for i in session.scalars(
                __import__("sqlalchemy").select(ContentItem)
            ).all()
            if i.run_id == run_id and i.status == ItemStatus.PENDING_REVIEW
        ]
    assert item_ids
    orch.approve(item_ids[0])
    ref = orch.publish_item(item_ids[0])
    assert ref  # simulated publish ref in dev mode

    insight = orch.collect_analytics(run_id)
    assert insight.recommendations
    assert insight.next_topic_suggestions


def test_compliance_blocks_banned_claims():
    """The deterministic scan must block a guaranteed-returns claim regardless of LLM."""
    agent = VerificationAgent()
    bad = Script(
        platform="linkedin",
        format="insight post",
        hook="We get startups guaranteed funding, every time!",
        body="Work with us for assured business growth and guaranteed results.",
        cta="Sign up now",
    )
    result = agent.run(script=bad, creative={})
    assert result.passed is False
    assert result.compliance_ok is False
    assert any(i.category == "compliance" and i.severity == "blocker" for i in result.issues)


def test_only_approved_items_publish():
    orch = Orchestrator()
    run_id = orch.run_cycle(topic="budgeting")
    with session_scope() as session:
        import sqlalchemy

        item = next(
            i
            for i in session.scalars(sqlalchemy.select(ContentItem)).all()
            if i.run_id == run_id
        )
        item_id = item.id
    with pytest.raises(ValueError):
        orch.publish_item(item_id)  # not approved yet
