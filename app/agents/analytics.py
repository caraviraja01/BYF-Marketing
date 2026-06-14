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
    temperature = 0.4

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
                "Educational decision-guide content drove the most saves; pure list "
                "formats underperformed on depth signals."
            ),
            what_worked=[
                f"Highest saves on {best.get('platform', 'instagram')} — decision-framework carousels resonate.",
                "Honest, risk-aware framing earned thoughtful comments (high-quality engagement).",
            ],
            what_underperformed=[
                f"{worst.get('platform', 'twitter')} reach was soft — hook likely too generic.",
                "Long captions on short-form may be hurting completion.",
            ],
            recommendations=[
                "Double down on 'which option for whom' decision guides as a repeatable format.",
                "A/B test sharper, number-led first lines on X to lift reach.",
                "Tighten short-form scripts to one idea; move detail to the carousel/long-form.",
                "Add a consistent saveable summary slide to every carousel.",
            ],
            next_topic_suggestions=[
                "Emergency fund sizing framework",
                "Index vs active funds — honest trade-offs",
                "First ₹/$1,000 to invest: a beginner sequence",
                "Lifestyle creep: the 10-year compounding cost",
            ],
        )
