"""Agent 3 — Script / Copywriting.

Expands a single content idea into a platform-native, ready-to-publish script:
hook, body, CTA, hashtags and visual direction for the creative agent.
"""
from __future__ import annotations

from typing import Any

from ..schemas import ContentIdea, Script
from .base import BaseAgent


class ScriptAgent(BaseAgent[Script]):
    name = "script"
    role = "Scriptwriting — platform-native copy"
    output_model = Script
    temperature = 0.8

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
            "Write the full, publish-ready script for this content idea.\n\n"
            f"IDEA:\n{data}\n\n"
            f"Write natively for {data.get('platform')} as a {data.get('format')}. "
            "Provide: a refined hook, the full body (formatted for the platform — use "
            "line breaks / slide markers as appropriate), a soft CTA, 5–12 relevant "
            "hashtags, and clear visual direction for the designer. If specific financial "
            "instruments or returns are mentioned, append the brand's required disclaimer. "
            "For video formats, estimate duration in seconds."
        )

    def mock(self, *, idea: dict[str, Any] | ContentIdea, **_: Any) -> Script:
        data = idea.model_dump() if isinstance(idea, ContentIdea) else idea
        platform = data.get("platform", "instagram")
        fmt = data.get("format", "carousel")
        disclaimer = self.brand.compliance.get("required_disclaimer", "").strip()
        body = (
            f"{data.get('hook', 'Here is the simple way to decide.')}\n\n"
            "1) Start with your goal and time horizon — not the product.\n"
            "2) Match risk to that horizon: shorter = safer, longer = more growth-oriented.\n"
            "3) Only then compare options on cost, lock-in and tax treatment.\n\n"
            f"{data.get('key_message', 'Pick the tool that fits your plan, not the hype.')}\n\n"
            f"{disclaimer}"
        )
        return Script(
            platform=platform,
            format=fmt,
            hook=data.get("hook", "Stop guessing — here's the 30-second filter."),
            body=body,
            cta=data.get("cta", "Save this for later."),
            hashtags=[
                "#personalfinance",
                "#moneytips",
                "#investing",
                "#financialfreedom",
                "#beyondyourfinance",
                "#taxsaving",
                "#moneymindset",
            ],
            visual_direction=(
                "Clean, calm brand palette. Bold headline per slide, one idea each, "
                "large readable type, a simple icon or mini-chart to anchor each point. "
                "Final slide: CTA + disclaimer in small but legible text."
            ),
            estimated_duration_sec=45 if fmt in {"reel", "short", "video"} else None,
        )
