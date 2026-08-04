"""
PrintBar Kiosk Agent — Authenticator

Exchanges the raw API key for a JWT access token.
Called once at startup. Token is re-requested if it expires.
"""
from __future__ import annotations
import logging
import httpx
from app.config.settings import KioskSettings

from app.utils.retry import retry_with_backoff

logger = logging.getLogger(__name__)


class Authenticator:
    """Handles kiosk authentication with the PrintBar backend."""

    def __init__(self, settings: KioskSettings) -> None:
        self._settings = settings
        self._access_token: str | None = None

    async def authenticate(self) -> str:
        """
        Authenticates with the backend using the raw API key.

        Returns:
            JWT access token string.

        Raises:
            RuntimeError: If authentication fails.
        """
        url = f"{self._settings.backend_url}/api/v1/kiosks/auth"
        payload = {"kiosk_id": self._settings.kiosk_id, "api_key": self._settings.api_key}

        async def _do_auth():
            async with httpx.AsyncClient(timeout=10, verify=False) as client:
                resp = await client.post(url, json=payload)

            if resp.status_code != 200:
                raise RuntimeError(
                    f"Kiosk authentication failed: HTTP {resp.status_code} — {resp.text}"
                )

            data = resp.json().get("data", {})
            token = data.get("accessToken")
            if not token:
                raise RuntimeError("Authentication response missing accessToken")
            return token

        token = await retry_with_backoff(
            _do_auth,
            max_attempts=5,
            base_delay=2.0,
            label="kiosk_authentication",
        )

        self._access_token = token
        logger.info("kiosk_authenticated", kiosk_id=self._settings.kiosk_id)
        return token

    @property
    def token(self) -> str | None:
        """Returns the current access token."""
        return self._access_token

    def authorization_header(self) -> dict[str, str]:
        """Returns HTTP Authorization header dict."""
        if not self._access_token:
            raise RuntimeError("Not authenticated — call authenticate() first.")
        return {"Authorization": f"Bearer {self._access_token}"}
