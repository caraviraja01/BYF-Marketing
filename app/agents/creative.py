"""Agent 4 — Creative Generation.

Produces 3 distinct visual concepts for one idea (the human picks one). Writing the
concepts/briefs is cheap (LLM text); the actual asset is only generated for the
*selected* concept — all types (image, carousel, video) are rendered by Higgsfield.
"""
from __future__ import annotations

from typing import Any

from ..integrations.higgsfield import HiggsfieldConnector
from ..schemas import CreativeAsset, CreativeSet
from ..settings import get_settings
from .base import BaseAgent


class CreativeAgent(BaseAgent[CreativeSet]):
    name = "creative"
    role = "Creative — on-brand visuals & video via Higgsfield"
    output_model = CreativeSet
    n_variants = 3
    max_tokens = 8192  # three creative concepts in one response

    def __init__(self, *args: Any, higgsfield: HiggsfieldConnector | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.higgsfield = higgsfield or HiggsfieldConnector()
        s = get_settings()
        self.n_variants = max(1, s.byf_variants)
        self.fast = s.byf_fast_content

    def expertise(self) -> str:
        return (
            "You are an art director for a finance-education brand. You translate copy "
            "into clear visual concepts: choose a `type` (image | carousel | video) and "
            "give a tight, production-ready `brief`; for carousels provide `slides` (one "
            "idea each). You keep it clean, trustworthy and highly legible on mobile — "
            "never cluttered or hypey. The last slide/frame always carries the CTA and "
            "disclaimer."
        )

    def _source(self, idea: Any = None, script: Any = None) -> dict[str, Any]:
        src = idea if idea is not None else script
        if hasattr(src, "model_dump"):
            return src.model_dump()
        return src or {}

    def build_user_prompt(self, *, idea: Any = None, script: Any = None, **_: Any) -> str:
        data = self._source(idea, script)
        return (
            f"Design {self.n_variants} DISTINCT creative concepts for this content so a "
            "human can pick one.\n\n"
            f"CONTENT:\n{data}\n\n"
            f"Make the {self.n_variants} concepts genuinely different (e.g. a carousel, a "
            "single bold-stat image, and a short talking-head/animated video). For each: "
            "set a short `concept` label, the `type`, a concise `brief`, and `slides` for "
            "carousels. Set every variant's `status` to 'brief_only' and leave url fields "
            "null — the system generates the chosen one afterward. Return them under "
            "`variants`."
        )

    def mock(self, *, idea: Any = None, script: Any = None, **_: Any) -> CreativeSet:
        data = self._source(idea, script)
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

    def realize(self, asset: CreativeAsset, *, platform: str = "", fmt: str = "") -> CreativeAsset:
        """Generate the actual asset (image / carousel / video) via Higgsfield."""
        return self.higgsfield.produce(asset, platform=platform, fmt=fmt)
