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

    def generate_json(
        self,
        *,
        system: str,
        user: str,
        fast: bool = False,
        max_tokens: int = 4096,
    ) -> dict[str, Any]:
        """Call Claude and parse a JSON object from the response.

        The system prompt should instruct the model to reply with JSON only.
        Raises :class:`LLMError` in mock mode — callers must guard with ``enabled``.
        """
        if not self.enabled:
            raise LLMError("LLM disabled (no ANTHROPIC_API_KEY); use the agent mock path.")

        # Note: `temperature` is intentionally not sent — the latest Claude models
        # deprecate it. Add it back per-model only if you target an older model.
        resp = self._client.messages.create(  # type: ignore[union-attr]
            model=self.model_for(fast=fast),
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
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
