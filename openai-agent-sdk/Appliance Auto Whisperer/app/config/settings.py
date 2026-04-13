from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"

    # ── Vision LLM ────────────────────────────────────────────────────────────
    # VISION_PROVIDER: "auto" | "gemini" | "openai"
    # "auto" = prefer Gemini if GEMINI_API_KEY is set, else fall back to OpenAI.
    # Gemini Flash is free-tier (1500 req/day): https://aistudio.google.com/apikey
    vision_provider: Literal["auto", "gemini", "openai"] = "auto"
    gemini_api_key: str = ""  # Google AI Studio — free tier, supports vision
    gemini_model: str = "models/gemini-2.5-flash"  # override via GEMINI_MODEL in .env
    openai_api_key: str = ""  # Optional fallback — gpt-4o
    openai_vision_model: str = "gpt-4o"

    # ── Bright Data — Web Unlocker (proxy-based) ──────────────────────────────
    # Proxy URL: brd-customer-{customer_id}-zone-{zone}:{api_token}@brd.superproxy.io:22225
    brightdata_customer_id: str = ""
    brightdata_api_token: str = ""
    brightdata_zone: str = "web_unlocker1"

    # ── YouTube Data API v3 ───────────────────────────────────────────────────
    youtube_api_key: str = ""

    # ── Fetch.ai Agentverse ───────────────────────────────────────────────────
    agentverse_api_key: str = ""

    # ── Computed helpers ──────────────────────────────────────────────────────

    @property
    def active_vision_provider(self) -> str | None:
        """
        Returns which provider to actually use: "gemini", "openai", or None.
        - "auto"   → prefer Gemini if key present, else OpenAI, else None
        - "gemini" → require Gemini key
        - "openai" → require OpenAI key
        """
        p = self.vision_provider
        if p == "gemini":
            return "gemini" if self.gemini_api_key else None
        if p == "openai":
            return "openai" if self.openai_api_key else None
        # auto
        if self.gemini_api_key:
            return "gemini"
        if self.openai_api_key:
            return "openai"
        return None

    @property
    def brightdata_proxy_url(self) -> str | None:
        """Full proxy URL for Bright Data Web Unlocker, or None if not configured."""
        if not (self.brightdata_customer_id and self.brightdata_api_token):
            return None
        cid = self.brightdata_customer_id.strip()
        zone = (self.brightdata_zone or "web_unlocker1").strip()
        token = self.brightdata_api_token.strip()
        return f"http://brd-customer-{cid}-zone-{zone}:{token}@brd.superproxy.io:22225"


@lru_cache
def get_settings() -> Settings:
    return Settings()
