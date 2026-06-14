"""Base class shared by every agent.

Each agent declares a system prompt (its expertise + the brand), a user prompt
(the task for this run), and a ``mock`` implementation used when no API key is set.
The base handles the Claude call, JSON parsing, and validation into a typed schema.
"""
from __future__ import annotations

import logging
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ValidationError

from ..brand import BrandProfile, load_brand
from ..llm import LLMClient, LLMError, get_llm

OutT = TypeVar("OutT", bound=BaseModel)
log = logging.getLogger("byf.agents")


def _looks_malformed(raw: Any) -> bool:
    """Detect the intermittent case where the model leaks its raw tool-call markup
    (e.g. '</parameter>', '</invoke>') into a string field instead of returning
    clean structured data."""
    text = repr(raw)
    return "</parameter>" in text or "</invoke>" in text or "<invoke" in text


class BaseAgent(Generic[OutT]):
    name: str = "agent"
    role: str = ""           # one-line description shown in the UI / logs
    output_model: type[BaseModel]
    fast: bool = False       # use the cheaper model for high-volume agents
    # Generous ceiling so rich outputs (strategy calendars, 3-variant sets) are never
    # truncated mid-JSON. It's an upper bound — only actual output tokens are billed.
    max_tokens: int = 8192

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
        return (
            f"{self.expertise()}\n\n"
            f"=== BRAND PROFILE (Beyond Your Finance) ===\n"
            f"{self.brand.as_prompt_context()}\n\n"
            f"=== OUTPUT ===\n"
            f"Return your answer by calling the `emit_result` tool with arguments that "
            f"match its schema exactly. Do not write any prose outside the tool call."
        )

    max_retries: int = 3  # the model occasionally returns malformed structured output

    def run(self, **inputs: Any) -> OutT:
        if not self.llm.enabled:
            return self.mock(**inputs)  # type: ignore[return-value]

        system = self.system_prompt()
        user = self.build_user_prompt(**inputs)
        schema = self.output_model.model_json_schema()
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                raw = self.llm.generate_json(
                    system=system, user=user, schema=schema,
                    fast=self.fast, max_tokens=self.max_tokens,
                )
                if _looks_malformed(raw):
                    raise ValueError("structured output looks malformed (tag/format leak)")
                return self.output_model.model_validate(raw)  # type: ignore[return-value]
            except (ValidationError, ValueError, LLMError) as exc:
                last_error = exc
                log.warning("%s: attempt %d/%d failed (%s); retrying",
                            self.name, attempt, self.max_retries, type(exc).__name__)
        assert last_error is not None
        raise last_error

    def refine(self, *, previous: dict[str, Any], feedback: str,
               element_model: type[BaseModel] | None = None, **inputs: Any) -> BaseModel:
        """Revise a previous output to incorporate the user's change request.

        ``element_model`` lets variant agents refine a single item (one Script /
        CreativeAsset) rather than the whole set.
        """
        model = element_model or self.output_model
        if not self.llm.enabled:
            return self._mock_refine(previous, feedback, model)

        schema = model.model_json_schema()
        system = self.system_prompt()
        user = (
            "You previously produced this output:\n"
            f"{previous}\n\n"
            f"The user has requested these changes:\n\"{feedback}\"\n\n"
            "Return a REVISED version that fully incorporates the feedback while keeping "
            "everything else strong, accurate and on-brand. Call the emit_result tool."
        )
        last_error: Exception | None = None
        for _ in range(self.max_retries):
            try:
                raw = self.llm.generate_json(
                    system=system, user=user, schema=schema, fast=self.fast,
                    max_tokens=self.max_tokens,
                )
                if _looks_malformed(raw):
                    raise ValueError("malformed refine output")
                return model.model_validate(raw)
            except (ValidationError, ValueError, LLMError) as exc:
                last_error = exc
        assert last_error is not None
        raise last_error

    @staticmethod
    def _mock_refine(previous: dict[str, Any], feedback: str, model: type[BaseModel]) -> BaseModel:
        """Offline stand-in: annotate a text field so the change request is visible."""
        data = dict(previous)
        for key in ("rationale", "summary", "brief", "body", "hook", "concept", "angle"):
            if isinstance(data.get(key), str):
                data[key] = f"{data[key]}\n\n[Revised per request: {feedback}]"
                break
        try:
            return model.model_validate(data)
        except ValidationError:
            return model.model_validate(previous)
