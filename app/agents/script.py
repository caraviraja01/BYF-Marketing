"""Agent 3 — Script / Copywriting.

Expands a single content idea into a platform-native, ready-to-publish script:
hook, body, CTA, hashtags and visual direction for the creative agent.
"""
from __future__ import annotations

from typing import Any

from ..schemas import ContentIdea, Script, ScriptSet
from .base import BaseAgent


class ScriptAgent(BaseAgent[ScriptSet]):
    name = "script"
    role = "Scriptwriting — platform-native copy"
    output_model = ScriptSet
    n_variants = 3

    def expertise(self) -> str:
        return (
            "You are an elite direct-response copywriter for finance education. You write "
            "scroll-stopping hooks (first line earns the second), deliver one clear idea "
            "with concrete numbers and analogies, and close with a soft, non-pushy CTA. "
            "You write natively for each platform: punchy on-screen lines and a spoken "
            "voiceover for reels/shorts, tight slide copy for carousels, a strong opening "
            "tweet for threads, and a credible, story-led hook for LinkedIn. You always "
            "include the required compliance disclaimer when specific instruments or "
            "returns are mentioned, and you never imply guaranteed outcomes."
        )

    def build_user_prompt(self, *, idea: dict[str, Any] | ContentIdea, **_: Any) -> str:
        data = idea.model_dump() if isinstance(idea, ContentIdea) else idea
        return (
            f"Write {self.n_variants} DISTINCT, publish-ready script variants for this "
            "content idea so a human can pick the best one.\n\n"
            f"IDEA:\n{data}\n\n"
            f"Write natively for {data.get('platform')} as a {data.get('format')}. "
            f"Make the {self.n_variants} variants genuinely different in approach (e.g. "
            "story-led, data/number-led, contrarian/myth-bust) — set each variant's "
            "`angle` to a short label naming that approach. Each variant needs: a refined "
            "hook, the full body (platform-formatted, with line breaks / slide markers), a "
            "soft CTA, 5–12 relevant hashtags, and clear visual direction for the designer. "
            "If specific financial matters or numbers are mentioned, append the brand's "
            "required disclaimer. For video formats, estimate duration in seconds. "
            "Return them under the `variants` array."
        )

    def mock(self, *, idea: dict[str, Any] | ContentIdea, **_: Any) -> ScriptSet:
        data = idea.model_dump() if isinstance(idea, ContentIdea) else idea
        platform = data.get("platform", "instagram")
        fmt = data.get("format", "carousel")
        km = data.get("key_message", "Get your numbers boardroom-ready before you pitch.")
        cta = data.get("cta", "Schedule a CFO Strategy Call.")
        disclaimer = self.brand.compliance.get("required_disclaimer", "").strip().strip('"')
        dur = 45 if fmt in {"reel", "short", "video"} else None
        hashtags = [
            "#startupfinance", "#virtualcfo", "#fundraising",
            "#cashflow", "#founders", "#taxation", "#beyondyourfinance",
        ]
        vis = (
            "Clean, professional brand palette. Bold headline per slide, one idea each, "
            "large readable type, a simple icon or mini-chart/KPI per point. Final "
            "slide: CTA + disclaimer in small but legible text."
        )

        def build(angle: str, hook: str, steps: str) -> Script:
            return Script(
                angle=angle, platform=platform, format=fmt, hook=hook,
                body=f"{hook}\n\n{steps}\n\n{km}\n\n{disclaimer}",
                cta=cta, hashtags=hashtags, visual_direction=vis,
                estimated_duration_sec=dur,
            )

        return ScriptSet(variants=[
            build(
                "Checklist / practical",
                "Investors don't reject decks — they reject messy financials.",
                "1) Clean, reconciled books.\n2) Cash flow: runway, burn, 13-week forecast.\n"
                "3) Unit economics + a defensible model.\n4) GST/TDS/MCA filings up to date.",
            ),
            build(
                "Data / number-led",
                "73% of founders underestimate how long diligence takes. Here's the fix.",
                "→ Diligence-ready books save ~6 weeks pre-raise.\n→ A 13-week cash view kills"
                " 'how long is your runway?' surprises.\n→ Clean filings remove deal-blocking flags.",
            ),
            build(
                "Story / contrarian",
                "A great product won't save a messy cap table. Ask any founder who's raised.",
                "The pitch gets you the meeting. The numbers close the round.\n"
                "Tidy books, a clear model, and compliance in order signal a team investors trust.",
            ),
        ])
