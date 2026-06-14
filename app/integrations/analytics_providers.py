"""Analytics fetch connector.

Pulls post-performance metrics for published items so the Analytics agent can learn
from them. Stubbed with deterministic, plausible numbers (seeded by the item id) so
the feedback loop is demonstrable end-to-end; swap ``fetch_metrics`` for real
platform insights APIs when credentials exist.
"""
from __future__ import annotations

import random
from typing import Any

from ..schemas import PerformanceMetrics


class AnalyticsProvider:
    enabled = False  # flip on once real insights APIs are wired

    def fetch_metrics(self, *, platform: str, published_ref: str, seed: int = 0) -> PerformanceMetrics:
        if self.enabled:  # pragma: no cover
            return self._fetch_live(platform=platform, published_ref=published_ref)
        return self._mock_metrics(platform=platform, seed=seed)

    def _mock_metrics(self, *, platform: str, seed: int) -> PerformanceMetrics:
        rng = random.Random(f"{platform}:{seed}")
        impressions = rng.randint(2_000, 45_000)
        likes = int(impressions * rng.uniform(0.01, 0.06))
        comments = int(likes * rng.uniform(0.02, 0.12))
        shares = int(likes * rng.uniform(0.05, 0.2))
        saves = int(likes * rng.uniform(0.1, 0.5))
        clicks = int(impressions * rng.uniform(0.002, 0.02))
        follows = int(impressions * rng.uniform(0.0005, 0.005))
        engaged = likes + comments + shares + saves
        return PerformanceMetrics(
            platform=platform,
            impressions=impressions,
            likes=likes,
            comments=comments,
            shares=shares,
            saves=saves,
            clicks=clicks,
            follows=follows,
            engagement_rate=round(engaged / impressions * 100, 2) if impressions else 0.0,
        )

    def _fetch_live(self, *, platform: str, published_ref: str) -> PerformanceMetrics:  # pragma: no cover
        """TODO(real-api): call each platform's insights API for ``published_ref``."""
        raise NotImplementedError("Wire real platform insights APIs here.")

    def metrics_dict(self, *, platform: str, published_ref: str, seed: int = 0) -> dict[str, Any]:
        return self.fetch_metrics(platform=platform, published_ref=published_ref, seed=seed).model_dump()
