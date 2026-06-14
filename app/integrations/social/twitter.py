"""X / Twitter publisher (stub until credentials are added)."""
from __future__ import annotations

import os
from typing import Any

from .base import PublishResult, SocialPublisher


class TwitterPublisher(SocialPublisher):
    platform = "twitter"

    @property
    def configured(self) -> bool:
        return bool(
            os.getenv("TWITTER_ACCESS_TOKEN")
            and os.getenv("TWITTER_ACCESS_SECRET")
            and os.getenv("TWITTER_API_KEY")
        )

    def publish(self, *, script: dict[str, Any], creative: dict[str, Any]) -> PublishResult:
        if not self.configured:
            return self._not_configured()
        # TODO(real-api): use the X API v2 POST /2/tweets. For threads, post the first
        # tweet then chain replies via in_reply_to_tweet_id. Upload media via v1.1
        # media/upload and attach media_ids.
        raise NotImplementedError("Wire the X API v2 here.")
