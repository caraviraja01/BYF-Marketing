"""Canva connector.

Turns a creative brief into an actual design. Two modes:

* **brief-only** (default, no key): returns the brief unchanged so a human/designer
  can produce the asset — nothing is faked as "generated".
* **live** (``CANVA_API_KEY`` set): create a design from the brand template and
  populate it from the brief/slides.

The live path is intentionally a single, well-marked method so wiring the real
Canva API (or the Canva MCP tools available in this workspace) is a focused change.
"""
from __future__ import annotations

from ..schemas import CreativeAsset
from ..settings import get_settings


class CanvaConnector:
    def __init__(self) -> None:
        self._settings = get_settings()

    @property
    def enabled(self) -> bool:
        return bool(self._settings.canva_api_key and self._settings.canva_brand_template_id)

    def produce(self, asset: CreativeAsset) -> CreativeAsset:
        if not self.enabled:
            asset.status = "brief_only"
            return asset
        return self._generate_live(asset)

    def _generate_live(self, asset: CreativeAsset) -> CreativeAsset:  # pragma: no cover
        """Create the design in Canva from the brand template.

        TODO(real-api): call Canva's autofill/Connect API (or the Canva MCP
        ``create-design-from-brand-template`` + ``perform-editing-operations`` +
        ``export-design`` tools) using ``self._settings.canva_brand_template_id``
        and ``asset.slides`` / ``asset.brief``. Populate the fields below from the
        response, then return ``asset``.
        """
        raise NotImplementedError(
            "Live Canva generation not wired yet — see TODO in CanvaConnector._generate_live."
        )
