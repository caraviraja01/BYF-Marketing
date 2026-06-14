"""Higgsfield video-generation connector.

Generates short-form video from a creative brief. Higgsfield is image-to-video,
so the flow is: (optional) a starting image → submit a generation job → poll until
the job completes → store the resulting video URL.

Auth + endpoints follow the official Higgsfield API:
  base   : https://platform.higgsfield.ai
  header : Authorization: Key <KEY_ID>:<KEY_SECRET>
  submit : POST /v1/image2video/dop      {model, prompt, input_images:[...]}
  poll   : GET  /requests/{request_id}/status

Credentials come from env (HIGGSFIELD_API_KEY, HIGGSFIELD_SECRET). If the key is
already in "id:secret" form, the secret env is optional. Anything missing or any
error degrades gracefully to a brief — the pipeline never breaks because video
generation is slow or unavailable.
"""
from __future__ import annotations

import os
import time

import httpx

from ..schemas import CreativeAsset

BASE_URL = os.getenv("HIGGSFIELD_BASE_URL", "https://platform.higgsfield.ai")
SUBMIT_PATH = os.getenv("HIGGSFIELD_SUBMIT_PATH", "/v1/image2video/dop")
MODEL = os.getenv("HIGGSFIELD_MODEL", "dop-turbo")


class HiggsfieldConnector:
    def __init__(self) -> None:
        self._key = os.getenv("HIGGSFIELD_API_KEY")
        self._secret = os.getenv("HIGGSFIELD_SECRET")

    @property
    def enabled(self) -> bool:
        return bool(self._key)

    def _auth_header(self) -> str:
        # Accept either "id:secret" in the key, or separate key + secret envs.
        cred = self._key if ":" in (self._key or "") else f"{self._key}:{self._secret or ''}"
        return f"Key {cred}"

    def produce(self, asset: CreativeAsset, *, start_image_url: str | None = None,
                poll_timeout_sec: int = 180, poll_interval_sec: int = 5) -> CreativeAsset:
        """Generate a video for ``asset`` from its brief. Degrades to a brief on failure."""
        asset.provider = "higgsfield"
        if not self.enabled:
            asset.status = "brief_only"
            asset.error = "Higgsfield not configured (set HIGGSFIELD_API_KEY)."
            return asset
        try:
            request_id = self._submit(asset, start_image_url)
            asset.higgsfield_request_id = request_id
            video_url = self._poll(request_id, poll_timeout_sec, poll_interval_sec)
            if video_url:
                asset.asset_url = video_url
                asset.status = "generated"
            else:
                asset.status = "generating"  # still running past our wait window
            return asset
        except Exception as exc:  # never break the pipeline on a video error
            asset.status = "brief_only"
            asset.error = f"Higgsfield generation failed: {exc}"
            return asset

    def _submit(self, asset: CreativeAsset, start_image_url: str | None) -> str:
        payload: dict = {
            "input": {
                "model": MODEL,
                "prompt": asset.brief or asset.title,
            }
        }
        if start_image_url:
            payload["input"]["input_images"] = [
                {"type": "image_url", "image_url": start_image_url}
            ]
        with httpx.Client(base_url=BASE_URL, timeout=30) as client:
            resp = client.post(
                SUBMIT_PATH,
                headers={"Authorization": self._auth_header(), "Content-Type": "application/json"},
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
        request_id = data.get("request_id") or data.get("id")
        if not request_id:
            raise RuntimeError(f"No request_id in submit response: {data}")
        return request_id

    def _poll(self, request_id: str, timeout_sec: int, interval_sec: int) -> str | None:
        deadline = time.monotonic() + timeout_sec
        with httpx.Client(base_url=BASE_URL, timeout=30) as client:
            while time.monotonic() < deadline:
                resp = client.get(
                    f"/requests/{request_id}/status",
                    headers={"Authorization": self._auth_header()},
                )
                resp.raise_for_status()
                data = resp.json()
                status = (data.get("status") or "").lower()
                if status == "completed":
                    video = data.get("video") or {}
                    return video.get("url") or data.get("url")
                if status in {"failed", "nsfw"}:
                    raise RuntimeError(f"Higgsfield job {status}: {data}")
                time.sleep(interval_sec)
        return None  # still running; caller leaves status as 'generating'
