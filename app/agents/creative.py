"""Agent 4 — Creative Generation.

Produces the on-brand visual: it writes a creative brief / slide copy with the LLM,
then hands that to the Canva connector to generate the actual asset. When Canva
isn't configured it degrades gracefully to a detailed brief a designer can execute.
"""
from __future__ import annotations

from typing import Any

from ..integrations.canva import CanvaConnector
from ..schemas import CreativeAsset, Script
from .base import BaseAgent


class CreativeAgent(BaseAgent[CreativeAsset]):
    name = "creative"
    role = "Creative — on-brand visuals via Canva"
    output_model = CreativeAsset
    temperature = 0.7

    def __init__(self, *args: Any, canva: CanvaConnector | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.canva = canva or CanvaConnector()

    def expertise(self) -> str:
        return (
            "You are an art director for a finance-education brand. You translate copy "
            "into a clear visual concept: format (single image, multi-slide carousel, or "
            "video storyboard), a tight headline per slide/frame, and direction on colour, "
            "type hierarchy, iconography and data-viz. You keep it clean, trustworthy and "
            "highly legible on mobile — never cluttered or hypey. Carousels get 5–8 slides "
            "with one idea each; the last slide always carries the CTA and disclaimer."
        )

    def build_user_prompt(self, *, script: dict[str, Any] | Script, **_: Any) -> str:
        data = script.model_dump() if isinstance(script, Script) else script
        return (
            "Design the creative for this script.\n\n"
            f"SCRIPT:\n{data}\n\n"
            "Decide the creative `type` (image | carousel | video_brief), write a concise "
            "production-ready `brief`, and for carousels provide `slides` as a list of "
            "per-slide copy. Set `status` to 'brief_only' (the system will attempt Canva "
            "generation afterward). Leave url fields null."
        )

    def mock(self, *, script: dict[str, Any] | Script, **_: Any) -> CreativeAsset:
        data = script.model_dump() if isinstance(script, Script) else script
        fmt = data.get("format", "carousel")
        is_carousel = fmt in {"carousel"}
        return CreativeAsset(
            type="carousel" if is_carousel else ("video_brief" if "duration" in str(data) else "image"),
            status="brief_only",
            title=data.get("hook", "BYF creative"),
            brief=(
                "Brand palette, generous whitespace, bold mobile-first headlines. "
                "One idea per slide, simple icon/mini-chart per point. Disclaimer on the "
                "final slide in small but legible type."
            ),
            slides=[
                data.get("hook", "What investors check first."),
                "1) Clean, reconciled books.",
                "2) Cash flow: runway, burn & 13-week forecast.",
                "3) Unit economics & a defensible model.",
                "4) Compliance in order: GST, TDS, MCA.",
                f"{data.get('cta', 'Schedule a CFO Strategy Call.')}"
                "\n\nFor informational purposes only — not professional advice.",
            ]
            if is_carousel
            else [],
        )

    def run(self, **inputs: Any) -> CreativeAsset:  # type: ignore[override]
        asset = super().run(**inputs)
        # Hand the brief to Canva; the connector upgrades status + fills urls, or
        # leaves it as a brief if Canva isn't configured.
        return self.canva.produce(asset)
