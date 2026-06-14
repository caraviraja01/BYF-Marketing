"""YouTube publisher (stub until credentials are added)."""
from __future__ import annotations

import os
from typing import Any

from .base import PublishResult, SocialPublisher


class YouTubePublisher(SocialPublisher):
    platform = "youtube"

    @property
    def configured(self) -> bool:
        return bool(
            os.getenv("YOUTUBE_CLIENT_ID")
            and os.getenv("YOUTUBE_CLIENT_SECRET")
            and os.getenv("YOUTUBE_REFRESH_TOKEN")
        )

    def publish(self, *, script: dict[str, Any], creative: dict[str, Any]) -> PublishResult:
        if not self.configured:
            return self._not_configured()
        # TODO(real-api): use the YouTube Data API v3 videos.insert (resumable upload)
        # with an OAuth token refreshed from the stored refresh token; set title,
        # description (script body), tags and privacy status.
        raise NotImplementedError("Wire the YouTube Data API here.")
