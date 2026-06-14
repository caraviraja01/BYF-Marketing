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
        anchor = topic or "Getting your startup finances investor-ready before a raise"
        return ResearchBrief(
            summary=(
                "Founders are increasingly anxious about fundraising in a tighter capital "
                f"market and confused by what 'investor-ready financials' actually means. "
                f"'{anchor}' is a high-intent topic BYF can own with practical, CFO-grade "
                "guidance that generic CA firms and influencers don't provide."
            ),
            trending_topics=[
                TrendingTopic(
                    title=anchor,
                    why_now="Founders prepping for raises want a concrete due-diligence checklist.",
                    angle="A CFO's pre-raise checklist: the numbers and documents investors demand.",
                    relevance_score=9,
                ),
                TrendingTopic(
                    title="Cash flow runway: the metric founders track too late",
                    why_now="Tighter funding makes runway and burn the board's #1 question.",
                    angle="A simple 13-week cash flow framework any founder can run.",
                    relevance_score=8,
                ),
                TrendingTopic(
                    title="GST & TDS mistakes that quietly cost growing businesses",
                    why_now="Recurring compliance pain; high search and save intent for SMEs.",
                    angle="The 5 avoidable compliance slip-ups we see most, and how to fix them.",
                    relevance_score=8,
                ),
                TrendingTopic(
                    title="BRSR & ESG reporting: what listed companies must prepare now",
                    why_now="Tightening BRSR Core requirements create urgent reporting demand.",
                    angle="A plain-English readiness map for ESG disclosures and carbon accounting.",
                    relevance_score=7,
                ),
            ],
            competitor_insights=[
                CompetitorInsight(
                    competitor="CFO Bridge / The CFO Centre",
                    what_they_did="Authority LinkedIn posts on fractional-CFO value and case studies.",
                    performance_signal="Strong B2B engagement on outcome-led, founder-story content.",
                    takeaway="Lead with measurable business outcomes and real client scenarios.",
                ),
                CompetitorInsight(
                    competitor="Vakilsearch",
                    what_they_did="High-volume compliance/registration explainers across IG + YouTube.",
                    performance_signal="Great reach but generic; thin on strategic CFO depth.",
                    takeaway="Differentiate on strategic finance + fundraising, not just compliance how-tos.",
                ),
            ],
            content_gaps=[
                "Strategic CFO/fundraising depth vs generic compliance how-tos",
                "Outcome-led founder stories with real financial metrics",
                "Plain-English ESG/BRSR readiness content for Indian companies",
            ],
            recommended_focus=(
                f"Own the '{anchor}' conversation with a CFO-grade, practical guide, "
                "repurposed across LinkedIn, Instagram, YouTube and X."
            ),
        )
