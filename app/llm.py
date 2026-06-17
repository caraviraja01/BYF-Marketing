"""Claude client wrapper.

Wraps the Anthropic SDK with a single ``generate_json`` entry point that every
agent uses. When no API key is configured the client is *disabled* and each agent
falls back to its own realistic mock output, so the whole pipeline runs offline.
"""
from __future__ import annotations

import json
import re
from typing import Any

from .settings import get_settings

_JSON_BLOCK = re.compile(r"\{.*\}|\[.*\]", re.DOTALL)


class LLMError(RuntimeError):
    pass


class LLMClient:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._client = None
        if self._settings.llm_enabled:
            # Imported lazily so the package works without the SDK installed in mock mode.
            from anthropic import Anthropic

            self._client = Anthropic(api_key=self._settings.anthropic_api_key)

    @property
    def enabled(self) -> bool:
        return self._client is not None

    def model_for(self, *, fast: bool = False) -> str:
        return self._settings.byf_fast_model if fast else self._settings.byf_model

    def generate_text(
        self,
        *,
        system: str,
        messages: list[dict[str, str]] | None = None,
        user: str | None = None,
        fast: bool = False,
        max_tokens: int = 1500,
    ) -> str:
        """Free-form text answer from Claude (used by the public Q&A assistant).

        Pass either a single ``user`` string or a full ``messages`` list (so the
        assistant can answer with conversation history). Raises :class:`LLMError`
        in mock mode — callers must guard with ``enabled``.
        """
        if not self.enabled:
            raise LLMError("LLM disabled (no ANTHROPIC_API_KEY); use the mock answer path.")
        if messages is None:
            messages = [{"role": "user", "content": user or ""}]
        resp = self._client.messages.create(  # type: ignore[union-attr]
            model=self.model_for(fast=fast),
            max_tokens=max_tokens,
            system=system,
            messages=messages,
        )
        return "".join(block.text for block in resp.content if block.type == "text").strip()

    def generate_json(
        self,
        *,
        system: str,
        user: str,
        schema: dict[str, Any] | None = None,
        fast: bool = False,
        max_tokens: int = 4096,
    ) -> dict[str, Any]:
        """Get structured JSON back from Claude.

        When a JSON ``schema`` is given we use tool-calling (``tool_choice`` forces
        the model to "call" a tool whose input is the schema), so the result is
        guaranteed-valid JSON — no fragile text parsing. Falls back to parsing text
        if no schema is provided.

        Raises :class:`LLMError` in mock mode — callers must guard with ``enabled``.
        """
        if not self.enabled:
            raise LLMError("LLM disabled (no ANTHROPIC_API_KEY); use the agent mock path.")

        # Note: `temperature` is intentionally not sent — the latest Claude models
        # deprecate it. Add it back per-model only if you target an older model.
        kwargs: dict[str, Any] = dict(
            model=self.model_for(fast=fast),
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        if schema is not None:
            kwargs["tools"] = [
                {
                    "name": "emit_result",
                    "description": "Return the final structured result for this task.",
                    "input_schema": schema,
                }
            ]
            kwargs["tool_choice"] = {"type": "tool", "name": "emit_result"}

        resp = self._client.messages.create(**kwargs)  # type: ignore[union-attr]

        if schema is not None:
            for block in resp.content:
                if getattr(block, "type", None) == "tool_use" and block.name == "emit_result":
                    return dict(block.input)  # already-parsed, schema-shaped JSON
            # Fall through to text parsing if the model didn't use the tool.
        text = "".join(block.text for block in resp.content if block.type == "text")
        return _parse_json(text)


def _parse_json(text: str) -> dict[str, Any]:
    text = text.strip()
    # Strip markdown fences if present.
    if text.startswith("```"):
        text = text.strip("`")
        text = text[text.find("\n") + 1 :] if "\n" in text else text
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = _JSON_BLOCK.search(text)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError as exc:  # pragma: no cover - defensive
                raise LLMError(f"Could not parse JSON from model output: {exc}") from exc
        raise LLMError("Model did not return JSON.")


_singleton: LLMClient | None = None


def get_llm() -> LLMClient:
    global _singleton
    if _singleton is None:
        _singleton = LLMClient()
    return _singleton
