"""
PrintBar Backend — Security Utilities

Provides JWT generation/verification and password hashing using Argon2id.

Secrets are never hardcoded. All cryptographic operations depend on
settings loaded from environment variables.

Classes:
    JWTHandler: Creates and verifies JWT access and refresh tokens.
    PasswordHasher: Hashes and verifies passwords using Argon2id.
"""

from __future__ import annotations

import secrets
import string
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from argon2 import PasswordHasher as Argon2PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from jose import ExpiredSignatureError, JWTError, jwt

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class JWTHandler:
    """
    Handles creation and verification of JWT access and refresh tokens.

    Access tokens expire in 15 minutes (configurable).
    Refresh tokens expire in 30 days (configurable).

    Claims:
        sub: Subject identifier (user_id or kiosk_id as string)
        role: User role (GUEST, ADMIN, SUPER_ADMIN, KIOSK)
        session_id: Associated session UUID
        exp: Expiration timestamp
        iat: Issued-at timestamp
        jti: JWT ID (unique per token for replay protection)
    """

    def __init__(self) -> None:
        self._settings = get_settings()

    def create_access_token(
        self,
        subject: str | UUID,
        role: str,
        session_id: str | UUID | None = None,
        extra_claims: dict[str, Any] | None = None,
    ) -> str:
        """
        Creates a short-lived JWT access token.

        Args:
            subject: User or kiosk identifier.
            role: Authorization role string.
            session_id: Associated guest or admin session ID.
            extra_claims: Optional additional claims to embed.

        Returns:
            Signed JWT string.
        """
        return self._create_token(
            subject=str(subject),
            role=role,
            session_id=str(session_id) if session_id is not None else str(subject),
            expire_delta=timedelta(minutes=self._settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
            token_type="access",
            extra_claims=extra_claims or {},
        )

    def create_refresh_token(
        self,
        subject: str | UUID,
        role: str,
        session_id: str | UUID,
    ) -> str:
        """
        Creates a long-lived JWT refresh token.

        Refresh tokens should be stored hashed (SHA-256) in the database.
        They should never be logged.

        Args:
            subject: User or kiosk identifier.
            role: Authorization role string.
            session_id: Associated session ID.

        Returns:
            Signed JWT string.
        """
        return self._create_token(
            subject=str(subject),
            role=role,
            session_id=str(session_id),
            expire_delta=timedelta(days=self._settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
            token_type="refresh",
        )

    def verify_token(self, token: str) -> dict[str, Any]:
        """
        Verifies and decodes a JWT token.

        Args:
            token: Raw JWT string from the Authorization header or cookie.

        Returns:
            Decoded claims dictionary.

        Raises:
            ValueError: If token is expired or invalid. Never exposes raw JWTError.
        """
        try:
            payload = jwt.decode(
                token,
                self._settings.JWT_SECRET,
                algorithms=[self._settings.JWT_ALGORITHM],
                options={"leeway": 60},
            )
            return payload
        except ExpiredSignatureError:
            logger.warning("jwt_token_expired")
            raise ValueError("Token has expired.")
        except JWTError as exc:
            logger.warning("jwt_token_invalid", error=str(exc))
            raise ValueError("Token is invalid.")

    def _create_token(
        self,
        subject: str,
        role: str,
        session_id: str,
        expire_delta: timedelta,
        token_type: str,
        extra_claims: dict[str, Any] | None = None,
    ) -> str:
        now = datetime.now(tz=UTC)
        claims: dict[str, Any] = {
            "sub": subject,
            "role": role,
            "session_id": session_id,
            "type": token_type,
            "jti": secrets.token_hex(16),
            "iat": now,
            "exp": now + expire_delta,
        }
        if extra_claims:
            claims.update(extra_claims)

        return jwt.encode(
            claims,
            self._settings.JWT_SECRET,
            algorithm=self._settings.JWT_ALGORITHM,
        )


class PasswordHasher:
    """
    Password hashing using Argon2id.

    Argon2id is the OWASP-recommended algorithm for password hashing.
    Never use SHA-256, MD5, or bcrypt for new deployments.

    Admin passwords require:
        - Minimum 16 characters
        - At least one uppercase letter
        - At least one lowercase letter
        - At least one digit
        - At least one special character
    """

    def __init__(self) -> None:
        self._hasher = Argon2PasswordHasher(
            time_cost=3,
            memory_cost=65536,  # 64 MiB
            parallelism=4,
        )

    def hash(self, password: str) -> str:
        """
        Hashes a plaintext password using Argon2id.

        Args:
            password: The plaintext password to hash.

        Returns:
            Argon2id hash string (includes algorithm parameters).
        """
        return self._hasher.hash(password)

    def verify(self, hashed: str, password: str) -> bool:
        """
        Verifies a plaintext password against an Argon2id hash.

        Args:
            hashed: Stored hash from the database.
            password: Plaintext password to verify.

        Returns:
            True if the password matches, False otherwise.
        """
        try:
            return self._hasher.verify(hashed, password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False

    def needs_rehash(self, hashed: str) -> bool:
        """
        Checks whether a hash needs to be upgraded to the current parameters.

        Args:
            hashed: Stored hash string.

        Returns:
            True if the hash should be rehashed with current parameters.
        """
        return self._hasher.check_needs_rehash(hashed)

    @staticmethod
    def validate_admin_password(password: str) -> list[str]:
        """
        Validates that an admin password meets the security policy.

        Args:
            password: Plaintext password to validate.

        Returns:
            List of validation error messages. Empty list = valid.
        """
        errors: list[str] = []
        settings = get_settings()

        if len(password) < settings.ADMIN_PASSWORD_MIN_LENGTH:
            errors.append(
                f"Password must be at least {settings.ADMIN_PASSWORD_MIN_LENGTH} characters."
            )
        if not any(c.isupper() for c in password):
            errors.append("Password must contain at least one uppercase letter.")
        if not any(c.islower() for c in password):
            errors.append("Password must contain at least one lowercase letter.")
        if not any(c.isdigit() for c in password):
            errors.append("Password must contain at least one digit.")
        if not any(c in string.punctuation for c in password):
            errors.append("Password must contain at least one special character.")

        return errors


def generate_api_key(length_bytes: int = 64) -> str:
    """
    Generates a cryptographically secure API key for Raspberry Pi kiosks.

    Args:
        length_bytes: Number of random bytes (default 64, yields 128-char hex string).

    Returns:
        Hex-encoded random string.
    """
    return secrets.token_hex(length_bytes)


# Module-level singletons — use these throughout the application.
jwt_handler = JWTHandler()
password_hasher = PasswordHasher()
