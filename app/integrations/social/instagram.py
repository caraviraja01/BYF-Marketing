"""Instagram publisher (stub until credentials are added)."""
from __future__ import annotations

import os
from typing import Any

from .base import PublishResult, SocialPublisher


class InstagramPublisher(SocialPublisher):
    platform = "instagram"

    @property
    def configured(self) -> bool:
        return bool(
            os.getenv("INSTAGRAM_ACCESS_TOKEN")
            and os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID")
        )

    def publish(self, *, script: dict[str, Any], creative: dict[str, Any]) -> PublishResult:
        if not self.configured:
            return self._not_configured()
        # TODO(real-api): use the Instagram Graph API two-step flow —
        # POST /{ig-user-id}/media (create container with image/video + caption),
        # then POST /{ig-user-id}/media_publish. Carousels create child containers.
        raise NotImplementedError("Wire the Instagram Graph API here.")
