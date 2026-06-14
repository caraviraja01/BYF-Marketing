"""Shared interface for every social platform publisher.

A publisher takes an approved script + creative and pushes it live, returning a
reference (post id / URL). Concrete publishers are stubs until credentials exist;
they raise a clear, actionable error rather than silently faking a post.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class PublishResult:
    success: bool
    ref: str | None  # post id or URL
    detail: str


class SocialPublisher:
    platform: str = "base"

    @property
    def configured(self) -> bool:
        """True when the required credentials are present."""
        raise NotImplementedError

    def publish(self, *, script: dict[str, Any], creative: dict[str, Any]) -> PublishResult:
        raise NotImplementedError

    def _not_configured(self) -> PublishResult:
        return PublishResult(
            success=False,
            ref=None,
            detail=(
                f"{self.platform} publisher is not configured. Add credentials to .env "
                f"and implement {type(self).__name__}.publish to go live."
            ),
        )


def get_publisher(platform: str) -> SocialPublisher:
    from .instagram import InstagramPublisher
    from .linkedin import LinkedInPublisher
    from .twitter import TwitterPublisher
    from .youtube import YouTubePublisher

    registry: dict[str, type[SocialPublisher]] = {
        "linkedin": LinkedInPublisher,
        "instagram": InstagramPublisher,
        "youtube": YouTubePublisher,
        "twitter": TwitterPublisher,
        "x": TwitterPublisher,
    }
    cls = registry.get(platform.lower())
    if cls is None:
        raise ValueError(f"No publisher registered for platform '{platform}'.")
    return cls()
