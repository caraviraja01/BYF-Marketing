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
        focus = brief.get("recommended_focus", "Tax-saving options, explained simply")
        topic = (brief.get("trending_topics") or [{}])[0].get(
            "title", "Tax-saving investment options"
        )
        return ContentStrategy(
            rationale=(
                f"Anchor the cycle on the recommended focus — {focus} — and repurpose the "
                "core idea natively per channel to maximise reach without extra research."
            ),
            ideas=[
                ContentIdea(
                    title=f"{topic}: which one is right for you?",
                    pillar="tax_smart",
                    platform="instagram",
                    format="carousel",
                    funnel_stage="consideration",
                    hook="Stop guessing which tax-saver to pick. Here's the 30-second filter.",
                    key_message="Match the instrument to your goal, horizon and risk — not the hype.",
                    cta="Save this for tax season.",
                ),
                ContentIdea(
                    title=f"The honest take on {topic.lower()}",
                    pillar="myth_busting",
                    platform="linkedin",
                    format="insight post",
                    funnel_stage="awareness",
                    hook="Most 'tax-saving' advice optimises for the wrong thing.",
                    key_message="Tax efficiency should serve your financial goals, not replace them.",
                    cta="Follow for jargon-free money thinking.",
                ),
                ContentIdea(
                    title=f"{topic} in 60 seconds",
                    pillar="tax_smart",
                    platform="youtube",
                    format="short",
                    funnel_stage="awareness",
                    hook="Three tax-savers, one simple way to choose.",
                    key_message="A quick decision framework anyone can apply today.",
                    cta="Full explainer on the channel.",
                ),
                ContentIdea(
                    title=f"Thread: {topic} myths that cost you money",
                    pillar="myth_busting",
                    platform="twitter",
                    format="thread",
                    funnel_stage="awareness",
                    hook="5 tax-saving myths that quietly drain your wealth 🧵",
                    key_message="Bust the myths, give the honest framework.",
                    cta="Repost if this cleared things up.",
                ),
            ],
            posting_notes=(
                "Publish the Instagram carousel first as the flagship asset, then repurpose "
                "into the YouTube Short and X thread within 48h while the topic is warm. "
                "LinkedIn post goes out mid-week morning for B2B reach."
            ),
        )
