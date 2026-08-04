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
    ForgotPasswordRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    User,
)
from ..auth.session_bridge import (
    clear_active_session,
    get_active_session,
    set_active_session,
    update_access_token,
)
from ..auth.user_store import UserStore
from ..config.models import EmailConfig
from ..core.email_service import EmailService
from ..core.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])

_store: Optional[UserStore] = None
_email_service: Optional[EmailService] = None
_email_config: Optional[EmailConfig] = None


def init_auth_routes(user_store: UserStore, email_config: Optional[EmailConfig] = None) -> None:
    """Called from app startup to provide the shared UserStore and email config."""
    global _store, _email_service, _email_config
    _store = user_store
    _email_config = email_config or EmailConfig()
    _email_service = EmailService(_email_config)


def _get_store() -> UserStore:
    if _store is None:
        raise HTTPException(status_code=503, detail="Auth system not initialised")
    return _store


def _log_activity(user_id: str, event_type: str, description: str) -> None:
    """Best-effort activity logging; never raises."""
    try:
        from .app import app_state  # deferred import to avoid circular dependency
        activity_logger = app_state.get("activity_logger")
        if activity_logger:
            activity_logger.log(user_id, event_type, description)
    except Exception:
        pass


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
    _log_activity(row["id"], "login", f"User {row['email']} logged in")
    # Mark this user as the 'active' web session — lets the local voice
    # assistant discover who's logged in and act as their personal assistant.
    set_active_session(row["id"], row["email"], row["role"], access_token, refresh_token)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/logout")
async def logout(current_user: User = Depends(require_auth)):
    """Client-driven logout — records the activity event; token invalidation is client-side."""
    _log_activity(current_user.id, "logout", f"User {current_user.email} logged out")
    clear_active_session(current_user.id)
    return {"status": "logged out"}


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
    active = get_active_session()
    if active and active.get("user_id") == user_id:
        update_access_token(new_token)
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


@router.post("/forgot-password")
async def forgot_password(req: ForgotPasswordRequest):
    """Request a password reset link. Always returns 200 regardless of whether
    the email exists, to avoid leaking which emails are registered."""
    store = _get_store()
    row = store.get_by_email(req.email)
    if row and row["is_active"]:
        expire_minutes = _email_config.reset_token_expire_minutes if _email_config else 30
        token = store.create_reset_token(row["id"], expire_minutes)
        base_url = (_email_config.frontend_base_url if _email_config else "http://localhost:3000").rstrip("/")
        reset_link = f"{base_url}/reset-password?token={token}"
        if _email_service:
            _email_service.send_password_reset_email(row["email"], reset_link)
        logger.info(f"Password reset requested for {row['email']}")
    return {"status": "If that email is registered, a reset link has been sent."}


@router.post("/reset-password")
async def reset_password(req: ResetPasswordRequest):
    """Complete a password reset using a token from the forgot-password email."""
    store = _get_store()
    token_row = store.get_valid_reset_token(req.token)
    if not token_row:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    store.update_password(token_row["user_id"], req.new_password)
    store.consume_reset_token(req.token)

    user_row = store.get_by_id(token_row["user_id"])
    if user_row:
        logger.info(f"Password reset completed for {user_row['email']}")
        _log_activity(user_row["id"], "password_reset", f"User {user_row['email']} reset their password")
    return {"status": "password updated"}


@router.get("/voice-session")
async def voice_session():
    """Used by the local voice assistant to discover which user is currently
    logged into the web UI, and obtain a valid access token to act on their
    behalf. Returns 404 if nobody is logged in — the voice assistant should
    then refuse to act and ask the user to log in."""
    session = get_active_session()
    if session is None:
        raise HTTPException(status_code=404, detail="No user is currently logged in")

    access_token = session["access_token"]
    try:
        decode_token(access_token)
    except ValueError:
        # Access token expired — try the cached refresh token once.
        refresh_token = session.get("refresh_token")
        if not refresh_token:
            clear_active_session(session["user_id"])
            raise HTTPException(status_code=404, detail="Session expired — please log in again")
        try:
            payload = decode_token(refresh_token)
            if payload.get("type") != "refresh":
                raise ValueError("Not a refresh token")
        except ValueError:
            clear_active_session(session["user_id"])
            raise HTTPException(status_code=404, detail="Session expired — please log in again")

        store = _get_store()
        row = store.get_by_id(session["user_id"])
        if not row or not row["is_active"]:
            clear_active_session(session["user_id"])
            raise HTTPException(status_code=404, detail="Session expired — please log in again")

        access_token = create_access_token({"sub": row["id"], "role": row["role"]})
        update_access_token(access_token)

    return {
        "user_id": session["user_id"],
        "email": session["email"],
        "access_token": access_token,
    }


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
