"""Tracks the single 'active' web-UI session for this desktop instance.

RAGenie is a personal, single-machine assistant: the voice pipeline runs as a
separate local process and has no access to the browser's localStorage. This
module lets it discover "who is currently logged into the web UI" and act as
that user's personal assistant — without needing its own separate credentials.

Deliberately in-memory only: it is cleared on every server restart, which is
consistent with the JWT server-instance-binding in jwt_manager.py (all
sessions die on restart, requiring a fresh login).
"""
import threading
from typing import Dict, Optional

_lock = threading.Lock()
_active: Optional[Dict[str, str]] = None  # user_id, email, role, access_token, refresh_token


def set_active_session(
    user_id: str,
    email: str,
    role: str,
    access_token: str,
    refresh_token: Optional[str] = None,
) -> None:
    """Called on login — marks this user as the current 'active' session."""
    global _active
    with _lock:
        _active = {
            "user_id": user_id,
            "email": email,
            "role": role,
            "access_token": access_token,
            "refresh_token": refresh_token or "",
        }


def update_access_token(access_token: str) -> None:
    """Called on token refresh to keep the cached access token current."""
    global _active
    with _lock:
        if _active is not None:
            _active["access_token"] = access_token


def clear_active_session(user_id: Optional[str] = None) -> None:
    """Called on logout. If user_id is given, only clears when it matches the
    current active session (so one user's logout can't clear another's)."""
    global _active
    with _lock:
        if _active is None:
            return
        if user_id is None or _active.get("user_id") == user_id:
            _active = None


def get_active_session() -> Optional[Dict[str, str]]:
    with _lock:
        return dict(_active) if _active is not None else None
