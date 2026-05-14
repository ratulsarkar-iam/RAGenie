"""Authentication endpoints: register, login, refresh, me, change-password."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from ..auth.dependencies import require_auth, require_admin
from ..auth.jwt_manager import (
    create_access_token,
    create_refresh_token,
    decode_token,
)
from ..auth.models import (
    ChangePasswordRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    User,
)
from ..auth.user_store import UserStore
from ..core.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])

_store: Optional[UserStore] = None


def init_auth_routes(user_store: UserStore) -> None:
    """Called from app startup to provide the shared UserStore."""
    global _store
    _store = user_store


def _get_store() -> UserStore:
    if _store is None:
        raise HTTPException(status_code=503, detail="Auth system not initialised")
    return _store


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.post("/register", status_code=201)
async def register(req: RegisterRequest):
    """Register a new user.

    The very first registered account is automatically granted the *admin* role.
    """
    store = _get_store()
    if store.email_exists(req.email):
        raise HTTPException(status_code=409, detail="Email already registered")

    role = "admin" if store.count_users() == 0 else "user"
    user = store.create_user(req.email, req.password, role)
    logger.info(f"Registered user: {user.email} role={role}")
    return {"user_id": user.id, "email": user.email, "role": user.role}


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest):
    """Authenticate and receive access + refresh tokens."""
    store = _get_store()
    row = store.get_by_email(req.email)

    if not row or not store.verify_password(req.password, row["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not row["is_active"]:
        raise HTTPException(status_code=403, detail="Account is disabled")

    store.update_last_login(row["id"])
    access_token = create_access_token({"sub": row["id"], "role": row["role"]})
    refresh_token = create_refresh_token(row["id"])
    logger.info(f"Login: {row['email']}")
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh")
async def refresh(req: RefreshRequest):
    """Exchange a refresh token for a new access token."""
    try:
        payload = decode_token(req.refresh_token)
        if payload.get("type") != "refresh":
            raise ValueError("Not a refresh token")
        user_id = payload["sub"]
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc))

    store = _get_store()
    row = store.get_by_id(user_id)
    if not row or not row["is_active"]:
        raise HTTPException(status_code=401, detail="User not found or disabled")

    new_token = create_access_token({"sub": user_id, "role": row["role"]})
    return {"access_token": new_token, "token_type": "bearer"}


@router.get("/me", response_model=User)
async def get_me(current_user: User = Depends(require_auth)):
    """Return the currently authenticated user's profile."""
    return current_user


@router.post("/change-password")
async def change_password(
    req: ChangePasswordRequest,
    current_user: User = Depends(require_auth),
):
    """Change the authenticated user's password."""
    store = _get_store()
    row = store.get_by_id(current_user.id)
    if not row or not store.verify_password(req.current_password, row["hashed_password"]):
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    store.update_password(current_user.id, req.new_password)
    logger.info(f"Password changed for user: {current_user.email}")
    return {"status": "password updated"}


@router.get("/users", response_model=list)
async def list_users(admin: User = Depends(require_admin)):
    """List all registered users (admin only)."""
    store = _get_store()
    import sqlite3
    with sqlite3.connect(store.db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, email, role, is_active, created_at, last_login FROM users"
        ).fetchall()
    return [dict(r) for r in rows]
