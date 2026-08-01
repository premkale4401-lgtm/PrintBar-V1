"""
PrintBar Backend — Application Configuration

All configuration is loaded exclusively from environment variables.
No secrets, URLs, or credentials are ever hardcoded.

Usage:
    from app.core.config import get_settings
    settings = get_settings()
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central configuration for the PrintBar FastAPI backend.

    All values are read from environment variables or a .env file.
    Production deployments must supply all required variables through
    the hosting platform's secret manager.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ─── Application ───────────────────────────────────────────────────────────
    APP_NAME: str = "PrintBar API"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = False

    # ─── API ───────────────────────────────────────────────────────────────────
    API_V1_PREFIX: str = "/api/v1"
    # Comma-separated string — parsed by validator into list.
    # Use str to prevent pydantic-settings from trying JSON parse on comma-separated values.
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    # ─── Database ──────────────────────────────────────────────────────────────
    DATABASE_URL: str = Field(
        ...,
        description="Async PostgreSQL connection string. Example: postgresql+asyncpg://user:pass@host/db",
    )
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    DATABASE_POOL_TIMEOUT: int = 30
    DATABASE_ECHO: bool = False

    # ─── Redis ─────────────────────────────────────────────────────────────────
    REDIS_URL: str = Field(
        ...,
        description="Redis connection URL. Example: redis://localhost:6379/0",
    )
    REDIS_MAX_CONNECTIONS: int = 20

    # ─── Supabase Storage ──────────────────────────────────────────────────────
    SUPABASE_URL: str = Field(..., description="Supabase project URL")
    SUPABASE_SERVICE_ROLE_KEY: str = Field(
        ...,
        description="Supabase service role key (never the anon key). Never exposed to frontend.",
    )
    STORAGE_BUCKET_PRINT_FILES: str = "print-files"
    STORAGE_BUCKET_RECEIPTS: str = "receipts"
    STORAGE_BUCKET_REPORTS: str = "reports"
    STORAGE_BUCKET_SYSTEM_ASSETS: str = "system-assets"
    SIGNED_URL_EXPIRY_SECONDS: int = 300  # 5 minutes

    # ─── JWT ───────────────────────────────────────────────────────────────────
    JWT_SECRET: str = Field(..., description="Secret key for signing JWTs. Min 64 chars.")
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # ─── Guest Session ─────────────────────────────────────────────────────────
    GUEST_SESSION_EXPIRE_HOURS: int = 24

    # ─── Easebuzz Payment (Legacy — kept for existing data, not active) ───────────
    EASEBUZZ_KEY: str = Field(default="", description="Easebuzz merchant key (legacy, not used)")
    EASEBUZZ_SALT: str = Field(default="", description="Easebuzz merchant salt (legacy, not used)")
    EASEBUZZ_BASE_URL: str = "https://pay.easebuzz.in"
    EASEBUZZ_ENV: Literal["test", "production"] = "test"
    PAYMENT_TIMEOUT_MINUTES: int = 15

    # ─── Razorpay Payment ──────────────────────────────────────────────────────
    RAZORPAY_KEY_ID: str = Field(
        ...,
        description="Razorpay Key ID (public — safe to return to frontend via API).",
    )
    RAZORPAY_KEY_SECRET: str = Field(
        ...,
        description=(
            "Razorpay Key Secret. NEVER exposed to the frontend. "
            "Used only for HMAC-SHA256 signature verification and order creation."
        ),
    )
    RAZORPAY_BASE_URL: str = "https://api.razorpay.com/v1"
    RAZORPAY_CURRENCY: str = "INR"

    # ─── WebSocket ─────────────────────────────────────────────────────────────
    WS_SECRET: str = Field(..., description="Shared secret for WebSocket message signing")
    WS_HEARTBEAT_INTERVAL_SECONDS: int = 30
    WS_KIOSK_OFFLINE_THRESHOLD_SECONDS: int = 90

    # ─── File Upload ───────────────────────────────────────────────────────────────
    MAX_FILE_SIZE_MB: int = 25
    MAX_PAGE_COUNT: int = 500

    # ─── Rate Limiting ─────────────────────────────────────────────────────────
    RATE_LIMIT_GUEST_PER_MINUTE: int = 60
    RATE_LIMIT_UPLOAD_PER_10_MINUTES: int = 5
    RATE_LIMIT_PAYMENT_PER_HOUR: int = 10
    RATE_LIMIT_ADMIN_LOGIN_PER_15_MINUTES: int = 5

    # ─── File Retention ────────────────────────────────────────────────────────
    FILE_RETENTION_AFTER_COMPLETION_DAYS: int = 30
    ABANDONED_UPLOAD_EXPIRY_MINUTES: int = 30
    FAILED_UPLOAD_EXPIRY_HOURS: int = 24
    CLEANUP_WORKER_INTERVAL_MINUTES: int = 15

    # ─── Security ──────────────────────────────────────────────────────────────
    KIOSK_API_KEY_LENGTH_BYTES: int = 64
    ADMIN_PASSWORD_MIN_LENGTH: int = 16

    # ─── Monitoring ────────────────────────────────────────────────────────────
    ENABLE_METRICS: bool = True

    @field_validator("JWT_SECRET")
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters long")
        return v

    @property
    def allowed_origins_list(self) -> list[str]:
        """Returns ALLOWED_ORIGINS as a list of strings."""
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"

    @property
    def max_file_size_bytes(self) -> int:
        return self.MAX_FILE_SIZE_MB * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    """
    Returns a cached Settings instance.

    The cache ensures a single instance is created per process,
    avoiding repeated environment variable reads.
    """
    return Settings()  # type: ignore[call-arg]
