"""Application configuration, loaded from environment / .env."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Claude
    anthropic_api_key: str | None = None
    byf_model: str = "claude-opus-4-8"
    byf_fast_model: str = "claude-haiku-4-5-20251001"

    # App
    byf_db_url: str = f"sqlite:///{ROOT / 'data' / 'byf.db'}"
    byf_env: str = "development"
    brand_file: Path = ROOT / "config" / "brand.yaml"

    # Canva
    canva_api_key: str | None = None
    canva_brand_template_id: str | None = None

    # Dashboard auth. Login is enforced only when a password is set, so local dev
    # stays open while a hosted deployment can be protected by setting BYF_AUTH_PASSWORD.
    byf_auth_username: str = "admin"
    byf_auth_password: str | None = None
    byf_secret_key: str | None = None

    @property
    def llm_enabled(self) -> bool:
        """True when a real Claude key is present; otherwise agents run in mock mode."""
        return bool(self.anthropic_api_key)

    @property
    def auth_enabled(self) -> bool:
        return bool(self.byf_auth_password)


@lru_cache
def get_settings() -> Settings:
    return Settings()
