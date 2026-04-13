"""
backend/config/settings.py

Loads all runtime configuration from the .env file via pydantic-settings.
Imported as a singleton `settings` throughout the backend.
"""

from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Odoo ─────────────────────────────────────────────────────────────────
    ODOO_URL: str = "http://educare-connect.me"
    ODOO_DB: str = "erpsight"
    ODOO_USERNAME: str = "admin"
    ODOO_PASSWORD: str = "admin"
    ODOO_REQUEST_TIMEOUT: int = 30   # seconds per RPC call
    ODOO_MAX_RETRIES: int = 3        # max retry attempts on transient error

    # ── AI / LLM (placeholder — configured by AI team) ───────────────────────
    GEMINI_API_KEY: Optional[str] = None

    # ── Firebase (placeholder — configured by AI team) ────────────────────────
    FIREBASE_CREDENTIALS_PATH: Optional[str] = None
    FIREBASE_DATABASE_URL: Optional[str] = None

    # ── Detection thresholds ──────────────────────────────────────────────────
    ZSCORE_THRESHOLD: float = 2.5          # |Z| >= this → anomaly
    CONFIDENCE_THRESHOLD: float = 0.85     # minimum to auto-execute action
    MIN_DAYS_OF_STOCK: int = 3             # stockout alert when below this
    MARGIN_RISK_THRESHOLD: float = 0.05    # alert if margin% < 5%
    CHURN_OVERDUE_FACTOR: float = 1.2      # overdue > 20% of avg cycle → churn

    # ── Scheduler ─────────────────────────────────────────────────────────────
    POLLING_INTERVAL_MINUTES: int = 15

    # ── Logging ───────────────────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"


settings = Settings()
