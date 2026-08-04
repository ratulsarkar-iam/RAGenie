"""JWT access and refresh token generation / validation using PyJWT."""
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import jwt

_SECRET = os.getenv("RAGENIE_SECRET_KEY", "dev-secret-change-in-production-please")
_ALGORITHM = "HS256"

# Generated fresh every time this module is (re-)imported, i.e. on every server
# startup. Embedding it in every token and rejecting mismatches on decode means
# all previously-issued tokens (access + refresh) are invalidated when the
# server restarts, forcing users to log in again — even though JWTs are
# otherwise stateless and would normally keep validating on a fixed secret.
_SERVER_INSTANCE_ID = secrets.token_hex(16)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(
    payload: Dict[str, Any],
    expires_minutes: int = 30,
) -> str:
    data = {**payload, "srv": _SERVER_INSTANCE_ID, "exp": _now() + timedelta(minutes=expires_minutes)}
    return jwt.encode(data, _SECRET, algorithm=_ALGORITHM)


def create_refresh_token(user_id: str, expires_days: int = 7) -> str:
    data = {
        "sub": user_id,
        "type": "refresh",
        "srv": _SERVER_INSTANCE_ID,
        "exp": _now() + timedelta(days=expires_days),
    }
    return jwt.encode(data, _SECRET, algorithm=_ALGORITHM)


def decode_token(token: str) -> Dict[str, Any]:
    """Decode and verify a JWT.

    Raises:
        ValueError: if the token is expired, invalid, or was issued by a
            previous server process (i.e. the server has restarted since).
    """
    try:
        payload = jwt.decode(token, _SECRET, algorithms=[_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise ValueError("Token has expired")
    except jwt.InvalidTokenError as exc:
        raise ValueError(f"Invalid token: {exc}")

    if payload.get("srv") != _SERVER_INSTANCE_ID:
        raise ValueError("Session invalidated by server restart — please log in again")
    return payload
