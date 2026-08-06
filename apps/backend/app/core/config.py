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
        default="sqlite+aiosqlite:///printbar.db",
        description="Async PostgreSQL connection string or SQLite for development. Example: postgresql+asyncpg://user:pass@host/db",
    )
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    DATABASE_POOL_TIMEOUT: int = 30
    DATABASE_ECHO: bool = False

    # ─── Redis ─────────────────────────────────────────────────────────────────
    REDIS_URL: str = Field(
        default="",
        description="Redis connection URL. Example: redis://localhost:6379/0. Optional in development.",
    )
    REDIS_MAX_CONNECTIONS: int = 20

    # ─── Supabase Storage ──────────────────────────────────────────────────────
    SUPABASE_URL: str = Field(
        default="", description="Supabase project URL. Optional in development."
    )
    SUPABASE_SERVICE_ROLE_KEY: str = Field(
        default="",
        description="Supabase service role key (never the anon key). Optional in development.",
    )
    STORAGE_BUCKET_PRINT_FILES: str = "print-files"
    STORAGE_BUCKET_RECEIPTS: str = "receipts"
    STORAGE_BUCKET_REPORTS: str = "reports"
    STORAGE_BUCKET_SYSTEM_ASSETS: str = "system-assets"
    SIGNED_URL_EXPIRY_SECONDS: int = 300  # 5 minutes

    # ─── JWT ───────────────────────────────────────────────────────────────────
    JWT_SECRET: str = Field(
        default="dev_secret_key_needs_64_characters" + "a" * 30,
        description="Secret key for signing JWTs. Min 64 chars.",
    )
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # ─── Guest Session ─────────────────────────────────────────────────────────
    GUEST_SESSION_EXPIRE_HOURS: int = 24

    # ─── Payment Provider ──────────────────────────────────────────────────────
    # Controls which payment gateway is active.
    # "mock"     — No gateway required. Use "Complete Payment" button in the UI.
    # "razorpay" — Requires RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET below.
    # "easebuzz" — Legacy. Requires EASEBUZZ_KEY and EASEBUZZ_SALT below.
    PAYMENT_PROVIDER: Literal["mock", "razorpay", "easebuzz"] = "mock"
    MOCK_PAYMENT_DELAY_SECONDS: float = 0.0

    # ─── Easebuzz Payment (Legacy — kept for existing data, not active) ───────────
    EASEBUZZ_KEY: str = Field(default="", description="Easebuzz merchant key (legacy, not used)")
    EASEBUZZ_SALT: str = Field(default="", description="Easebuzz merchant salt (legacy, not used)")
    EASEBUZZ_BASE_URL: str = "https://pay.easebuzz.in"
    EASEBUZZ_ENV: Literal["test", "production"] = "test"
    PAYMENT_TIMEOUT_MINUTES: int = 15

    # ─── Razorpay Payment ──────────────────────────────────────────────────────
    # Required only when PAYMENT_PROVIDER=razorpay.
    RAZORPAY_KEY_ID: str = Field(
        default="",
        description="Razorpay Key ID (public — safe to return to frontend via API).",
    )
    RAZORPAY_KEY_SECRET: str = Field(
        default="",
        description=(
            "Razorpay Key Secret. NEVER exposed to the frontend. "
            "Used only for HMAC-SHA256 signature verification and order creation."
        ),
    )
    RAZORPAY_WEBHOOK_SECRET: str = Field(
        default="",
        description=(
            "Razorpay Webhook Signing Secret. NEVER exposed. "
            "Different from KEY_SECRET. Used to verify incoming webhook payloads. "
            "Configure in Razorpay Dashboard → Webhooks."
        ),
    )
    RAZORPAY_BASE_URL: str = "https://api.razorpay.com/v1"
    RAZORPAY_CURRENCY: str = "INR"

    # ─── WebSocket ─────────────────────────────────────────────────────────────
    WS_SECRET: str = Field(
        default="dev_ws_secret_needs_32_chars_123",
        description="Shared secret for WebSocket message signing",
    )
    WS_HEARTBEAT_INTERVAL_SECONDS: int = 30
    WS_KIOSK_OFFLINE_THRESHOLD_SECONDS: int = 90

    # ─── Development / Testing ─────────────────────────────────────────────────
    # MUST be False when a real Raspberry Pi kiosk is connected.
    # Enabling this with real hardware causes race conditions and ghost completions.
    ENABLE_SIMULATED_KIOSK: bool = Field(
        default=False,
        description=(
            "Enables the simulated kiosk background worker for development testing "
            "WITHOUT a real Raspberry Pi. MUST be False when real hardware is present. "
            "Ignored in production regardless of value."
        ),
    )

    # ─── Worker Tuning ─────────────────────────────────────────────────────────
    JOB_DISPATCH_WORKER_INTERVAL_SECONDS: int = Field(
        default=30,
        description="How often the belt-and-suspenders job dispatch worker polls (seconds).",
    )
    RECOVERY_WORKER_INTERVAL_SECONDS: int = Field(
        default=60,
        description="How often the workflow recovery worker checks for stuck jobs (seconds).",
    )

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

    # ─── Backend Base URL (used for local-storage fallback signed URLs) ────────
    # In development: the Raspberry Pi must be able to reach this URL over the LAN.
    # Example: http://192.168.1.100:8000
    # Defaults to localhost — override in kiosk's network environment.
    BACKEND_BASE_URL: str = Field(
        default="http://localhost:8000",
        description=(
            "Fully-qualified base URL of the backend server. "
            "Used only when SUPABASE_URL is not set (local-storage dev mode) "
            "to build download URLs the Raspberry Pi can reach over the LAN."
        ),
    )

    @field_validator("JWT_SECRET")
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        """Enforces a minimum JWT secret length to prevent weak signing keys."""
        if len(v) < 64:
            raise ValueError("JWT_SECRET must be at least 64 characters long")
        return v

    def validate_payment_provider_credentials(self) -> None:
        """
        Enforces that gateway credentials are set when a real provider is selected.

        Called at application startup to fail fast if configuration is incomplete.
        Mock mode requires no credentials and is always safe.
        """
        if self.PAYMENT_PROVIDER == "razorpay":
            if not self.RAZORPAY_KEY_ID or not self.RAZORPAY_KEY_SECRET:
                raise ValueError(
                    "PAYMENT_PROVIDER=razorpay requires RAZORPAY_KEY_ID and "
                    "RAZORPAY_KEY_SECRET to be set in the environment."
                )
        elif self.PAYMENT_PROVIDER == "easebuzz":
            if not self.EASEBUZZ_KEY or not self.EASEBUZZ_SALT:
                raise ValueError(
                    "PAYMENT_PROVIDER=easebuzz requires EASEBUZZ_KEY and "
                    "EASEBUZZ_SALT to be set in the environment."
                )

    def validate_all(self) -> None:
        """
        Validates the entire configuration for correctness at startup.
        Fails fast if any required dependency or configuration is invalid.
        """
        self.validate_payment_provider_credentials()

        if self.is_production:
            if not self.SUPABASE_URL.startswith("http"):
                raise ValueError("Production requires a valid SUPABASE_URL")
            if not self.REDIS_URL.startswith("redis"):
                raise ValueError("Production requires a valid REDIS_URL")
            if not self.DATABASE_URL.startswith("postgresql+asyncpg"):
                raise ValueError("Production requires a valid asyncpg PostgreSQL connection string")
            if not self.SUPABASE_SERVICE_ROLE_KEY:
                raise ValueError("Production requires SUPABASE_SERVICE_ROLE_KEY")
            if self.JWT_SECRET.startswith("dev_secret_key"):
                raise ValueError("Production requires a secure, non-default JWT_SECRET")
            if self.WS_SECRET.startswith("dev_ws_secret"):
                raise ValueError("Production requires a secure, non-default WS_SECRET")

        if self.SUPABASE_URL and not self.SUPABASE_URL.startswith("http"):
            raise ValueError("SUPABASE_URL must be a valid HTTP/HTTPS URL")

        if self.REDIS_URL and not self.REDIS_URL.startswith("redis"):
            raise ValueError("REDIS_URL must be a valid Redis URL")

        if (
            not self.DATABASE_URL.startswith("postgresql+asyncpg")
            and "sqlite" not in self.DATABASE_URL
        ):
            raise ValueError(
                "DATABASE_URL must be a valid asyncpg PostgreSQL or SQLite connection string"
            )

        if not all(
            [
                self.STORAGE_BUCKET_PRINT_FILES,
                self.STORAGE_BUCKET_RECEIPTS,
                self.STORAGE_BUCKET_REPORTS,
                self.STORAGE_BUCKET_SYSTEM_ASSETS,
            ]
        ):
            raise ValueError("All storage buckets must be configured (cannot be empty)")

        if len(self.WS_SECRET) < 32:
            raise ValueError("WS_SECRET must be at least 32 characters long")

        if len(self.JWT_SECRET) < 64:
            raise ValueError("JWT_SECRET must be at least 64 characters long")

        if not self.ALLOWED_ORIGINS:
            raise ValueError("ALLOWED_ORIGINS cannot be empty")

    @property
    def is_mock_payment(self) -> bool:
        """True when the mock payment provider is active."""
        return self.PAYMENT_PROVIDER == "mock"

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
