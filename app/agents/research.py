"""Agent 1 — Market Research.

Finds timely, trending finance topics and studies competitor content to surface
angles and content gaps for Beyond Your Finance.
"""
from __future__ import annotations

from typing import Any

from ..schemas import CompetitorInsight, ResearchBrief, TrendingTopic
from .base import BaseAgent


class ResearchAgent(BaseAgent[ResearchBrief]):
    name = "research"
    role = "Market Research — trends & competitor analysis"
    output_model = ResearchBrief
    fast = True
    temperature = 0.6

    def expertise(self) -> str:
        return (
            "You are a senior social-media market researcher specialising in the "
            "personal-finance niche. You spot timely, high-engagement topics before "
            "they peak, and you reverse-engineer why competitor content works. "
            "You think in terms of audience pain points, search/▲trend signals, "
            "seasonality (tax dates, budget announcements, new-year resolutions), and "
            "content gaps a brand can credibly own. You are sceptical of hype and you "
            "flag anything that would push the brand into risky or non-compliant claims."
        )

    def build_user_prompt(
        self,
        *,
        topic: str | None = None,
        web_signals: dict[str, Any] | None = None,
        recent_analytics: list[dict[str, Any]] | None = None,
        **_: Any,
    ) -> str:
        parts = ["Produce a market-research brief for the next content cycle."]
        if topic:
            parts.append(f"\nSeed topic to anchor the research around: '{topic}'.")
        else:
            parts.append("\nNo seed topic — propose the strongest opportunities yourself.")
        if web_signals:
            parts.append(f"\nLive trend/competitor signals to ground your analysis:\n{web_signals}")
        if recent_analytics:
            parts.append(
                "\nWhat our recent content did (use to avoid repetition and double down "
                f"on what worked):\n{recent_analytics}"
            )
        parts.append(
            "\nReturn 4–6 trending topics (each with a BYF angle and a 1–10 relevance "
            "score), 2–4 competitor insights, concrete content gaps, and one clear "
            "recommended focus for this cycle."
        )
        return "\n".join(parts)

    def mock(self, *, topic: str | None = None, **_: Any) -> ResearchBrief:
        anchor = topic or "Tax-saving investment options for salaried earners"
        return ResearchBrief(
            summary=(
                "Tax-planning season interest is rising and audiences are confused by "
                f"jargon-heavy comparisons. '{anchor}' is a high-intent, evergreen "
                "opportunity BYF can own with plain-English explainers."
            ),
            trending_topics=[
                TrendingTopic(
                    title=anchor,
                    why_now="Recurring high-intent search spikes around tax deadlines.",
                    angle="Plain-English 'which one, for whom' decision guide — no jargon.",
                    relevance_score=9,
                ),
                TrendingTopic(
                    title="The real cost of lifestyle creep",
                    why_now="Evergreen pain point; strong save/share behaviour.",
                    angle="Show the 10-year compounding cost of small habit upgrades.",
                    relevance_score=8,
                ),
                TrendingTopic(
                    title="Emergency fund: how much is actually enough?",
                    why_now="Perennial beginner question, low competition for clear answers.",
                    angle="A simple framework tied to job stability and dependents.",
                    relevance_score=7,
                ),
                TrendingTopic(
                    title="Index funds vs active funds, explained simply",
                    why_now="Ongoing debate; great myth-busting territory.",
                    angle="Honest trade-offs with real numbers, no tribalism.",
                    relevance_score=8,
                ),
            ],
            competitor_insights=[
                CompetitorInsight(
                    competitor="Generic finance creators",
                    what_they_did="Fast-cut reels listing instruments with on-screen text.",
                    performance_signal="High reach but shallow saves; comments ask 'but which for me?'",
                    takeaway="Win on decision-making clarity, not just listing options.",
                ),
                CompetitorInsight(
                    competitor="Hype 'get-rich' accounts",
                    what_they_did="Bold return claims and FOMO hooks.",
                    performance_signal="Spiky reach, low trust, frequent backlash.",
                    takeaway="Differentiate on honesty and risk transparency — our moat.",
                ),
            ],
            content_gaps=[
                "Decision frameworks ('which option for which person') vs plain lists",
                "Honest risk/trade-off content that still feels encouraging",
                "Beginner-safe explainers that don't assume prior knowledge",
            ],
            recommended_focus=(
                f"Own the '{anchor}' conversation with a jargon-free decision guide, "
                "repurposed across all four channels."
            ),
        )
