"""PIN hashing and operator access tokens.

PIN hashing here is `sha256`, a placeholder — good enough to avoid storing
plain-text PINs during development, not a real password hash. A real
deployment should switch to argon2 (`pwdlib`/`passlib`) before going near
production; that's a Phase 9 hardening item, not implemented here.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt

from macenplast.config import get_settings
from macenplast.db.models import OperatorRole

_JWT_ALGORITHM = "HS256"


def hash_pin(pin: str) -> str:
    """Hash a PIN for storage. See module docstring on hash strength."""
    return hashlib.sha256(pin.encode("utf-8")).hexdigest()


def verify_pin(pin: str, pin_hash: str) -> bool:
    """Check a plaintext PIN against a stored hash."""
    return hash_pin(pin) == pin_hash


@dataclass(frozen=True)
class TokenPayload:
    """Decoded contents of an access token."""

    operator_id: uuid.UUID
    role: OperatorRole


class InvalidTokenError(Exception):
    """Raised when a token is missing, expired, or malformed."""


def create_access_token(operator_id: uuid.UUID, role: OperatorRole) -> str:
    """Issue a signed access token for one shift (see `access_token_ttl_minutes`)."""
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(operator_id),
        "role": role.value,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_ttl_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=_JWT_ALGORITHM)


def decode_access_token(token: str) -> TokenPayload:
    """Verify and decode an access token.

    Raises:
        InvalidTokenError: if the token is missing, expired, malformed, or
            has an invalid signature.
    """
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[_JWT_ALGORITHM])
        return TokenPayload(
            operator_id=uuid.UUID(payload["sub"]),
            role=OperatorRole(payload["role"]),
        )
    except (jwt.InvalidTokenError, KeyError, ValueError) as exc:
        raise InvalidTokenError(str(exc)) from exc
