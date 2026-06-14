"""Agent 2 — Content Strategy.

Turns the research brief into a concrete set of content ideas, mapped to brand
pillars, channels, formats and funnel stages.
"""
from __future__ import annotations

from typing import Any

from ..schemas import ContentIdea, ContentStrategy, ResearchBrief
from .base import BaseAgent


class StrategyAgent(BaseAgent[ContentStrategy]):
    name = "strategy"
    role = "Content Strategy — pillars, cadence & ideas"
    output_model = ContentStrategy
    temperature = 0.65

    def expertise(self) -> str:
        return (
            "You are a veteran content strategist who has grown finance brands across "
            "LinkedIn, Instagram, YouTube and X. You translate research into a focused "
            "content plan: you choose the right format for each platform (carousels and "
            "reels on Instagram, threads and hot takes on X, long-form + Shorts on "
            "YouTube, insight posts on LinkedIn), map every idea to a brand pillar and a "
            "funnel stage (awareness/consideration/conversion), and you avoid spreading "
            "thin — one strong core idea repurposed beats five weak ones. You respect the "
            "configured channels and weekly cadence."
        )

    def build_user_prompt(
        self,
        *,
        research: dict[str, Any] | ResearchBrief,
        items_per_run: int = 4,
        **_: Any,
    ) -> str:
        brief = research.model_dump() if isinstance(research, ResearchBrief) else research
        channels = ", ".join(self.brand.enabled_channels) or "linkedin, instagram, youtube, twitter"
        return (
            "Using the research brief below, design a content plan for this cycle.\n\n"
            f"RESEARCH BRIEF:\n{brief}\n\n"
            f"Produce exactly {items_per_run} content ideas spread across these enabled "
            f"channels: {channels}. Lead with the recommended focus, then diversify. "
            "Each idea must include the pillar id, platform, format, funnel stage, a "
            "scroll-stopping hook, the single key message, and a soft CTA. Add brief "
            "posting notes (sequencing / repurposing advice)."
        )

    def mock(self, *, research: dict[str, Any] | ResearchBrief, **_: Any) -> ContentStrategy:
        brief = research if isinstance(research, dict) else research.model_dump()
        focus = brief.get("recommended_focus", "Getting startup finances investor-ready")
        topic = (brief.get("trending_topics") or [{}])[0].get(
            "title", "Getting your startup finances investor-ready"
        )
        return ContentStrategy(
            rationale=(
                f"Anchor the cycle on the recommended focus — {focus} — and repurpose the "
                "core idea natively per channel. Lead on LinkedIn (where founders and "
                "decision-makers are) and support with educational social formats."
            ),
            ideas=[
                ContentIdea(
                    title=f"{topic}: a CFO's pre-raise checklist",
                    pillar="startup_finance",
                    platform="linkedin",
                    format="insight post",
                    funnel_stage="consideration",
                    hook="Investors don't reject decks — they reject messy financials. Here's the fix.",
                    key_message="The documents and metrics every founder needs ready before a raise.",
                    cta="Schedule a CFO Strategy Call.",
                ),
                ContentIdea(
                    title="The 13-week cash flow framework founders track too late",
                    pillar="virtual_cfo",
                    platform="instagram",
                    format="carousel",
                    funnel_stage="awareness",
                    hook="Profit ≠ cash. The metric that actually keeps you alive 👇",
                    key_message="A simple rolling cash flow view that prevents nasty surprises.",
                    cta="Download the Startup Finance Checklist.",
                ),
                ContentIdea(
                    title="Investor-ready financials in 60 seconds",
                    pillar="startup_finance",
                    platform="youtube",
                    format="short",
                    funnel_stage="awareness",
                    hook="What investors check first in your financials.",
                    key_message="A quick walkthrough of the must-haves before due diligence.",
                    cta="Full fundraising explainer on the channel.",
                ),
                ContentIdea(
                    title="Thread: GST & TDS mistakes that cost growing businesses",
                    pillar="taxation",
                    platform="twitter",
                    format="thread",
                    funnel_stage="awareness",
                    hook="5 compliance slip-ups quietly draining growing businesses 🧵",
                    key_message="Common, avoidable errors — and the practical fix for each.",
                    cta="Connect with Our Finance Experts.",
                ),
            ],
            posting_notes=(
                "Lead with the LinkedIn insight post mid-week morning for founder/B2B reach, "
                "then repurpose into the Instagram carousel and YouTube Short within 48h "
                "while the topic is warm. Run the X thread to capture taxation-update search interest."
            ),
        )
