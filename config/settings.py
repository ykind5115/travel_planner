"""Application settings loaded from environment variables."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings:
    # ── LLM ──────────────────────────────────────────────
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "mock")
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "https://api.minimax.chat/v1")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "MiniMax-M2.7")
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.7"))
    LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "4096"))

    # ── Pipeline ─────────────────────────────────────────
    BUDGET_MAX_RETRIES: int = int(os.getenv("BUDGET_MAX_RETRIES", "3"))
    PARALLEL_TIMEOUT: int = int(os.getenv("PARALLEL_TIMEOUT", "30"))

    # ── API Server ───────────────────────────────────────
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    API_BASE_URL: str = os.getenv("API_BASE_URL", f"http://localhost:{API_PORT}")

    # ── Logging ──────────────────────────────────────────
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # ── Tool Provider Switches: mock / real ──────────────
    FLIGHT_API_PROVIDER: str = os.getenv("FLIGHT_API_PROVIDER", "mock")
    HOTEL_API_PROVIDER: str = os.getenv("HOTEL_API_PROVIDER", "mock")
    WEATHER_API_PROVIDER: str = os.getenv("WEATHER_API_PROVIDER", "mock")
    ACTIVITY_API_PROVIDER: str = os.getenv("ACTIVITY_API_PROVIDER", "mock")

    # ── Amadeus (Flight + Hotel) ─────────────────────────
    AMADEUS_CLIENT_ID: str = os.getenv("AMADEUS_CLIENT_ID", "")
    AMADEUS_CLIENT_SECRET: str = os.getenv("AMADEUS_CLIENT_SECRET", "")
    AMADEUS_ENV: str = os.getenv("AMADEUS_ENV", "sandbox")

    # ── OpenWeatherMap ───────────────────────────────────
    OPENWEATHER_API_KEY: str = os.getenv("OPENWEATHER_API_KEY", "")

    # ── Google Places ────────────────────────────────────
    GOOGLE_PLACES_API_KEY: str = os.getenv("GOOGLE_PLACES_API_KEY", "")

    @property
    def amadeus_base_url(self) -> str:
        return (
            "https://test.api.amadeus.com"
            if self.AMADEUS_ENV == "sandbox"
            else "https://api.amadeus.com"
        )


settings = Settings()
