"""Higgsfield connector — generates images AND video for creatives.

Higgsfield is the sole creative provider (no Canva). Flow per type:
  * image    → text-to-image  (one job)
  * carousel → text-to-image per slide
  * video    → text-to-image cover, then image-to-video

All jobs are async: submit → poll until completed. Auth + endpoints follow the
official Higgsfield API:
  base   : https://platform.higgsfield.ai
  header : Authorization: Key <KEY_ID>:<KEY_SECRET>
  image  : POST /v1/text2image/soul
  video  : POST /v1/image2video/dop
  poll   : GET  /requests/{request_id}/status

Credentials come from env (HIGGSFIELD_API_KEY, HIGGSFIELD_SECRET). If the key is
already "id:secret", the secret env is optional. Any error or missing key degrades
gracefully to a brief — the pipeline never breaks because generation is slow or
the host is unreachable.
"""
from __future__ import annotations

import logging
import os
import time

import httpx

from ..schemas import CreativeAsset

log = logging.getLogger("byf.higgsfield")

BASE_URL = os.getenv("HIGGSFIELD_BASE_URL", "https://platform.higgsfield.ai")
IMAGE_PATH = os.getenv("HIGGSFIELD_IMAGE_PATH", "/v1/text2image/soul")
VIDEO_PATH = os.getenv("HIGGSFIELD_VIDEO_PATH", "/v1/image2video/dop")
VIDEO_MODEL = os.getenv("HIGGSFIELD_VIDEO_MODEL", "dop-turbo")

# Aspect ratio per platform/format.
def _aspect(platform: str, fmt: str) -> str:
    f = (fmt or "").lower()
    p = (platform or "").lower()
    if f in {"reel", "short", "story"} or p in {"instagram", "youtube"} and "short" in f:
        return "9:16"
    if p == "youtube":
        return "16:9"
    if f == "carousel":
        return "4:5"
    return "1:1"


class HiggsfieldConnector:
    def __init__(self) -> None:
        self._key = os.getenv("HIGGSFIELD_API_KEY")
        self._secret = os.getenv("HIGGSFIELD_SECRET")

    @property
    def enabled(self) -> bool:
        return bool(self._key)

    def _headers(self) -> dict[str, str]:
        cred = self._key if ":" in (self._key or "") else f"{self._key}:{self._secret or ''}"
        return {"Authorization": f"Key {cred}", "Content-Type": "application/json"}

    # ── Public entry point ─────────────────────────────────────────────────────
    def produce(self, asset: CreativeAsset, *, platform: str = "", fmt: str = "") -> CreativeAsset:
        asset.provider = "higgsfield"
        if not self.enabled:
            asset.status = "brief_only"
            asset.error = "Higgsfield not connected — set HIGGSFIELD_API_KEY (and HIGGSFIELD_SECRET)."
            return asset
        try:
            ar = _aspect(platform, fmt or asset.type)
            if asset.type == "video":
                cover = self._image(asset.brief or asset.title, "9:16")
                video = self._video(asset.brief or asset.title, cover)
                asset.asset_url, asset.thumbnail_url, asset.status = video, cover, "generated"
            elif asset.type == "carousel":
                prompts = asset.slides or [asset.brief or asset.title]
                urls = [self._image(f"{asset.brief}\n\nSlide: {s}", ar) for s in prompts[:6]]
                asset.slide_urls = [u for u in urls if u]
                asset.asset_url = asset.slide_urls[0] if asset.slide_urls else None
                asset.status = "generated" if asset.slide_urls else "brief_only"
            else:  # image
                asset.asset_url = self._image(asset.brief or asset.title, ar)
                asset.status = "generated" if asset.asset_url else "brief_only"
            return asset
        except Exception as exc:  # never break the pipeline
            log.exception("Higgsfield generation failed")
            asset.status = "brief_only"
            asset.error = f"Higgsfield generation failed: {exc}"
            return asset

    # ── Internals ──────────────────────────────────────────────────────────────
    def _image(self, prompt: str, aspect_ratio: str) -> str | None:
        payload = {"params": {"prompt": prompt[:1500], "aspect_ratio": aspect_ratio, "safety_tolerance": 2}}
        rid = self._submit(IMAGE_PATH, payload)
        return self._poll(rid)

    def _video(self, prompt: str, start_image_url: str | None) -> str | None:
        inp: dict = {"model": VIDEO_MODEL, "prompt": prompt[:1500]}
        if start_image_url:
            inp["input_images"] = [{"type": "image_url", "image_url": start_image_url}]
        rid = self._submit(VIDEO_PATH, {"params": inp})
        return self._poll(rid)

    def _submit(self, path: str, payload: dict) -> str:
        with httpx.Client(base_url=BASE_URL, timeout=30) as client:
            resp = client.post(path, headers=self._headers(), json=payload)
            resp.raise_for_status()
            data = resp.json()
        rid = data.get("request_id") or data.get("id") or (data.get("jobs") or [{}])[0].get("id")
        if not rid:
            raise RuntimeError(f"No request_id in submit response: {str(data)[:200]}")
        return rid

    def _poll(self, request_id: str, timeout_sec: int = 240, interval_sec: int = 5) -> str | None:
        deadline = time.monotonic() + timeout_sec
        with httpx.Client(base_url=BASE_URL, timeout=30) as client:
            while time.monotonic() < deadline:
                resp = client.get(f"/requests/{request_id}/status", headers=self._headers())
                resp.raise_for_status()
                data = resp.json()
                status = (data.get("status") or "").lower()
                if status == "completed":
                    media = data.get("video") or data.get("image") or data.get("result") or {}
                    if isinstance(media, dict):
                        return media.get("url") or media.get("raw", {}).get("url") or data.get("url")
                    return data.get("url")
                if status in {"failed", "nsfw"}:
                    raise RuntimeError(f"Higgsfield job {status}")
                time.sleep(interval_sec)
        return None
