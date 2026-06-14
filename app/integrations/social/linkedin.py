"""LinkedIn publisher (stub until credentials are added)."""
from __future__ import annotations

import os
from typing import Any

from .base import PublishResult, SocialPublisher


class LinkedInPublisher(SocialPublisher):
    platform = "linkedin"

    @property
    def configured(self) -> bool:
        return bool(os.getenv("LINKEDIN_ACCESS_TOKEN") and os.getenv("LINKEDIN_ORG_URN"))

    def publish(self, *, script: dict[str, Any], creative: dict[str, Any]) -> PublishResult:
        if not self.configured:
            return self._not_configured()
        # TODO(real-api): POST to LinkedIn UGC/Posts API (/rest/posts) with the
        # access token + org URN; attach the creative as an image/video asset.
        raise NotImplementedError("Wire the LinkedIn Posts API here.")
