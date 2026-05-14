"""JWT access and refresh token generation / validation using PyJWT."""
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import jwt

_SECRET = os.getenv("RAGENIE_SECRET_KEY", "dev-secret-change-in-production-please")
_ALGORITHM = "HS256"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(
    payload: Dict[str, Any],
    expires_minutes: int = 30,
) -> str:
    data = {**payload, "exp": _now() + timedelta(minutes=expires_minutes)}
    return jwt.encode(data, _SECRET, algorithm=_ALGORITHM)


def create_refresh_token(user_id: str, expires_days: int = 7) -> str:
    data = {
        "sub": user_id,
        "type": "refresh",
        "exp": _now() + timedelta(days=expires_days),
    }
    return jwt.encode(data, _SECRET, algorithm=_ALGORITHM)


def decode_token(token: str) -> Dict[str, Any]:
    """Decode and verify a JWT.

    Raises:
        ValueError: if the token is expired or invalid.
    """
    try:
        return jwt.decode(token, _SECRET, algorithms=[_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise ValueError("Token has expired")
    except jwt.InvalidTokenError as exc:
        raise ValueError(f"Invalid token: {exc}")
