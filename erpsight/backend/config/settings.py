"""
backend/config/settings.py

Loads all runtime configuration from the .env file via pydantic-settings.
Imported as a singleton `settings` throughout the backend.

The .env file is resolved relative to the project root (ERPSight/.env),
so this module works correctly regardless of the working directory.
"""

from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Odoo (required — must be set in .env) ────────────────────────────────
    ODOO_URL: str
    ODOO_DB: str
    ODOO_USERNAME: str
    ODOO_PASSWORD: str
    ODOO_REQUEST_TIMEOUT: int = 30   # seconds per XML-RPC call
    ODOO_MAX_RETRIES: int = 3        # max retry attempts on transient error

    # ── AI / LLM (optional — configured by AI team) ──────────────────────────
    GEMINI_API_KEY: Optional[str] = None
    # gemini-2.0-flash  → free tier, 1500 req/day (recommended)
    # gemini-1.5-flash  → free tier, backup
    # gemini-2.5-pro    → paid only (free tier limit = 0)
    GEMINI_MODEL: str = "gemini-2.0-flash"

    # Groq (free tier, 14 400 req/day — recommended alternative to Gemini)
    # Sign up free: https://console.groq.com → API Keys → Create key
    # Paste key here and Gemini will NOT be used (Groq takes priority)
    # Best model: llama-3.3-70b-versatile (smart + fast)
    GROQ_API_KEY: Optional[str] = None
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    # ── Firebase (optional — configured by AI team) ───────────────────────────
    FIREBASE_CREDENTIALS_PATH: Optional[str] = None
    FIREBASE_DATABASE_URL: Optional[str] = None

    # ── Detection thresholds ──────────────────────────────────────────────────
    ZSCORE_THRESHOLD: float = 2.5           # |Z| >= this → anomaly flag
    CONFIDENCE_THRESHOLD: float = 0.85      # minimum to auto-execute action
    MIN_DAYS_OF_STOCK: int = 3              # stockout alert when below this
    MARGIN_RISK_THRESHOLD: float = 0.05     # alert if gross margin < 5%
    CHURN_OVERDUE_FACTOR: float = 1.2       # overdue > 120% of avg cycle → churn

    # ── Scheduler ─────────────────────────────────────────────────────────────
    POLLING_INTERVAL_MINUTES: int = 15

    # ── Logging ───────────────────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"


settings = Settings()
