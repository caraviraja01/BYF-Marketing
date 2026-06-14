"""Agent 6 — Analytics & Optimisation.

After content is published, this agent reads the performance metrics and produces
insights + concrete recommendations that feed back into the next research/strategy
cycle — closing the loop.
"""
from __future__ import annotations

from typing import Any

from ..schemas import AnalyticsInsight, PerformanceMetrics
from .base import BaseAgent


class AnalyticsAgent(BaseAgent[AnalyticsInsight]):
    name = "analytics"
    role = "Analytics — traction tracking & optimisation"
    output_model = AnalyticsInsight
    fast = True

    def expertise(self) -> str:
        return (
            "You are a growth analyst for social media. You read engagement metrics in "
            "context (reach vs saves vs shares vs follows tell different stories), "
            "distinguish signal from noise, and translate numbers into clear, prioritised "
            "actions. You compare against the content's goal and funnel stage, identify "
            "which hooks/formats/topics over- and under-performed, and recommend specific, "
            "testable changes for the next cycle. You avoid vanity-metric thinking."
        )

    def build_user_prompt(self, *, metrics: list[dict[str, Any]], **_: Any) -> str:
        return (
            "Analyse the performance of our recently published content and recommend what "
            "to do differently next cycle.\n\n"
            f"METRICS (one record per published item):\n{metrics}\n\n"
            "Return a headline read, what worked, what underperformed, prioritised "
            "recommendations, and 3–5 next-topic suggestions to feed the research agent."
        )

    def mock(self, *, metrics: list[dict[str, Any]], **_: Any) -> AnalyticsInsight:
        best = max(metrics, key=lambda m: m.get("saves", 0), default={})
        worst = min(metrics, key=lambda m: m.get("engagement_rate", 0), default={})
        return AnalyticsInsight(
            headline=(
                "Founder-focused, outcome-led content drove the strongest qualified "
                "engagement; generic compliance how-tos underperformed on depth."
            ),
            what_worked=[
                f"Highest engagement on {best.get('platform', 'linkedin')} — CFO checklists and frameworks resonate with founders.",
                "Practical, metric-led posts earned high-intent comments and consultation enquiries.",
            ],
            what_underperformed=[
                f"{worst.get('platform', 'twitter')} reach was soft — hook likely too generic.",
                "Long captions on short-form may be hurting completion.",
            ],
            recommendations=[
                "Double down on CFO checklists and decision frameworks as a repeatable LinkedIn format.",
                "Lead more posts with a measurable business outcome or a real client scenario.",
                "A/B test sharper, number-led first lines on X to lift reach.",
                "Add a consistent saveable summary slide + soft CTA to every carousel.",
            ],
            next_topic_suggestions=[
                "13-week cash flow forecasting for founders",
                "Due-diligence data room: what investors ask for",
                "GST & TDS compliance calendar for SMEs",
                "BRSR Core readiness for listed companies",
                "When should a startup hire a Virtual CFO?",
            ],
        )
