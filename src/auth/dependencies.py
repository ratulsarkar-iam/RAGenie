"""FastAPI dependency injection helpers for authentication."""
from typing import Optional

from fastapi import Depends, Header, HTTPException

from .jwt_manager import decode_token
from .models import User
from .user_store import UserStore

_user_store: Optional[UserStore] = None
_auth_enabled: bool = False


def set_user_store(store: UserStore) -> None:
    """Called during app startup to inject the shared UserStore."""
    global _user_store
    _user_store = store


def set_auth_enabled(enabled: bool) -> None:
    """Called during app startup to toggle auth enforcement globally."""
    global _auth_enabled
    _auth_enabled = enabled


def _row_to_user(row: dict) -> User:
    return User(
        id=row["id"],
        email=row["email"],
        role=row["role"],
        is_active=bool(row["is_active"]),
        created_at=row.get("created_at", ""),
        last_login=row.get("last_login"),
    )


async def get_current_user_optional(
    authorization: Optional[str] = Header(None),
) -> Optional[User]:
    """Return the authenticated user or ``None`` if no valid token supplied."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization[7:]
    try:
        payload = decode_token(token)
        if payload.get("type") == "refresh":
            return None
        if _user_store is None:
            return None
        row = _user_store.get_by_id(payload["sub"])
        if not row or not row["is_active"]:
            return None
        return _row_to_user(row)
    except Exception:
        return None


async def require_auth(
    user: Optional[User] = Depends(get_current_user_optional),
) -> User:
    """Require a valid Bearer token. Raises 401 otherwise."""
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def require_admin(user: User = Depends(require_auth)) -> User:
    """Require admin role. Raises 403 otherwise."""
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


async def require_auth_when_enabled(
    user: Optional[User] = Depends(get_current_user_optional),
) -> Optional[User]:
    """Enforce auth only when ``auth.enabled=true`` in config.

    Allows unauthenticated access in dev/local deployments (auth disabled).
    Raises 401 in production (auth enabled) when no valid Bearer token is supplied.
    """
    if _auth_enabled and user is None:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
