"""Base class shared by every agent.

Each agent declares a system prompt (its expertise + the brand), a user prompt
(the task for this run), and a ``mock`` implementation used when no API key is set.
The base handles the Claude call, JSON parsing, and validation into a typed schema.
"""
from __future__ import annotations

import json
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from ..brand import BrandProfile, load_brand
from ..llm import LLMClient, get_llm

OutT = TypeVar("OutT", bound=BaseModel)


class BaseAgent(Generic[OutT]):
    name: str = "agent"
    role: str = ""           # one-line description shown in the UI / logs
    output_model: type[BaseModel]
    fast: bool = False       # use the cheaper model for high-volume agents
    temperature: float = 0.7
    max_tokens: int = 4096

    def __init__(self, brand: BrandProfile | None = None, llm: LLMClient | None = None) -> None:
        self.brand = brand or load_brand()
        self.llm = llm or get_llm()

    # ── To implement in subclasses ────────────────────────────────────────────
    def expertise(self) -> str:
        """The agent's persona + instructions (everything except brand + schema)."""
        raise NotImplementedError

    def build_user_prompt(self, **inputs: Any) -> str:
        raise NotImplementedError

    def mock(self, **inputs: Any) -> OutT:
        raise NotImplementedError

    # ── Shared machinery ───────────────────────────────────────────────────────
    def system_prompt(self) -> str:
        schema = json.dumps(self.output_model.model_json_schema(), indent=2)
        return (
            f"{self.expertise()}\n\n"
            f"=== BRAND PROFILE (Beyond Your Finance) ===\n"
            f"{self.brand.as_prompt_context()}\n\n"
            f"=== OUTPUT FORMAT ===\n"
            f"Respond with a SINGLE valid JSON object only — no prose, no markdown "
            f"fences. It must conform to this JSON schema:\n{schema}"
        )

    def run(self, **inputs: Any) -> OutT:
        if not self.llm.enabled:
            return self.mock(**inputs)  # type: ignore[return-value]
        raw = self.llm.generate_json(
            system=self.system_prompt(),
            user=self.build_user_prompt(**inputs),
            fast=self.fast,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        return self.output_model.model_validate(raw)  # type: ignore[return-value]
