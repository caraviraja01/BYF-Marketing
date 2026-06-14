"""Web/trend research connector.

Supplies live trend + competitor signals to the Research agent. Stubbed by default;
wire a real source (Google Trends, platform search APIs, a SERP API, or the
WebSearch tool in an agent runtime) in ``fetch_signals``.
"""
from __future__ import annotations

from typing import Any


class WebResearchConnector:
    enabled = False  # flip on once a real source is wired

    def fetch_signals(self, topic: str | None = None) -> dict[str, Any] | None:
        """Return trend/competitor signals, or None to let the agent reason unaided.

        TODO(real-api): query a trends/search source and return a compact dict, e.g.
        {"rising_queries": [...], "competitor_posts": [...], "seasonality": "..."}.
        """
        if not self.enabled:
            return None
        raise NotImplementedError("Wire a real trends/search source here.")
