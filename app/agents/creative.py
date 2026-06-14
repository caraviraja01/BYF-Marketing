"""Agent 4 — Creative Generation.

Produces 3 distinct visual concepts for one idea (the human picks one). Writing the
concepts/briefs is cheap (LLM text); the actual asset is only generated for the
*selected* concept, routed to Canva (images / carousels) or Higgsfield (video).
"""
from __future__ import annotations

from typing import Any

from ..integrations.canva import CanvaConnector
from ..integrations.higgsfield import HiggsfieldConnector
from ..schemas import CreativeAsset, CreativeSet, Script
from .base import BaseAgent


class CreativeAgent(BaseAgent[CreativeSet]):
    name = "creative"
    role = "Creative — on-brand visuals via Canva & Higgsfield"
    output_model = CreativeSet
    n_variants = 3

    def __init__(
        self,
        *args: Any,
        canva: CanvaConnector | None = None,
        higgsfield: HiggsfieldConnector | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.canva = canva or CanvaConnector()
        self.higgsfield = higgsfield or HiggsfieldConnector()

    def expertise(self) -> str:
        return (
            "You are an art director for a finance-education brand. You translate copy "
            "into clear visual concepts: choose a `type` (image | carousel | video) and "
            "give a tight, production-ready `brief`; for carousels provide `slides` (one "
            "idea each). You keep it clean, trustworthy and highly legible on mobile — "
            "never cluttered or hypey. The last slide/frame always carries the CTA and "
            "disclaimer."
        )

    def build_user_prompt(self, *, script: dict[str, Any] | Script, **_: Any) -> str:
        data = script.model_dump() if isinstance(script, Script) else script
        return (
            f"Design {self.n_variants} DISTINCT creative concepts for this script so a "
            "human can pick one.\n\n"
            f"SCRIPT:\n{data}\n\n"
            f"Make the {self.n_variants} concepts genuinely different (e.g. a carousel, a "
            "single bold-stat image, and a short talking-head/animated video). For each: "
            "set a short `concept` label, the `type`, a concise `brief`, and `slides` for "
            "carousels. Set every variant's `status` to 'brief_only' and leave url fields "
            "null — the system generates the chosen one afterward. Return them under "
            "`variants`."
        )

    def mock(self, *, script: dict[str, Any] | Script, **_: Any) -> CreativeSet:
        data = script.model_dump() if isinstance(script, Script) else script
        hook = data.get("hook", "BYF creative")
        cta = data.get("cta", "Schedule a CFO Strategy Call.")
        disc = "For informational purposes only — not professional advice."
        return CreativeSet(variants=[
            CreativeAsset(
                concept="Educational carousel",
                type="carousel", status="brief_only", title=hook,
                brief="Brand palette, generous whitespace, bold mobile-first headlines. "
                      "One idea per slide, simple icon/mini-chart per point.",
                slides=[hook, "1) Clean, reconciled books.",
                        "2) Cash flow: runway, burn & 13-week forecast.",
                        "3) Unit economics & a defensible model.",
                        f"{cta}\n\n{disc}"],
            ),
            CreativeAsset(
                concept="Bold single-stat image",
                type="image", status="brief_only", title=hook,
                brief="One striking statistic centred on a clean brand-colour background, "
                      "supporting line beneath, small logo + disclaimer in the corner.",
            ),
            CreativeAsset(
                concept="Short talking-head / animated video",
                type="video", status="brief_only", title=hook,
                brief="15–30s vertical video: hook on-screen in first 2s, 3 quick points "
                      "with kinetic captions, end card with CTA + disclaimer. "
                      "Calm, credible pacing.",
            ),
        ])

    def realize(self, asset: CreativeAsset, *, start_image_url: str | None = None) -> CreativeAsset:
        """Generate the actual asset for a chosen concept via the right provider."""
        if asset.type == "video":
            return self.higgsfield.produce(asset, start_image_url=start_image_url)
        return self.canva.produce(asset)
