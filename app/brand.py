"""Loads and exposes the Beyond Your Finance brand profile (config/brand.yaml)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from .settings import get_settings


class BrandProfile(dict):
    """Thin dict wrapper with convenient accessors for the bits agents use most."""

    @property
    def name(self) -> str:
        return self.get("name", "Beyond Your Finance")

    @property
    def enabled_channels(self) -> list[str]:
        return [
            channel
            for channel, cfg in (self.get("channels") or {}).items()
            if cfg.get("enabled", False)
        ]

    @property
    def compliance(self) -> dict[str, Any]:
        return self.get("compliance", {})

    def as_prompt_context(self) -> str:
        """A compact, readable rendering of the brand for inclusion in system prompts."""
        return yaml.safe_dump(dict(self), sort_keys=False, allow_unicode=True).strip()


@lru_cache
def load_brand(path: str | Path | None = None) -> BrandProfile:
    brand_path = Path(path) if path else get_settings().brand_file
    with open(brand_path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return BrandProfile(data)
