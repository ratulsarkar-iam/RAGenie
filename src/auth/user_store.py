"""SQLite-backed user store with PBKDF2-SHA256 password hashing (stdlib only)."""
import hashlib
import secrets
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .models import User

_HASH_ALGO = "sha256"
_ITERATIONS = 260_000  # NIST SP 800-132 recommended minimum for PBKDF2-SHA256
_SALT_BYTES = 32


class UserStore:
    """Create, read, and authenticate users in a local SQLite database."""

    def __init__(self, db_path: str = "data/auth/users.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # ── Schema ──────────────────────────────────────────────────────────────

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id               TEXT PRIMARY KEY,
                    email            TEXT UNIQUE NOT NULL,
                    hashed_password  TEXT NOT NULL,
                    role             TEXT NOT NULL DEFAULT 'user',
                    is_active        INTEGER NOT NULL DEFAULT 1,
                    created_at       TEXT NOT NULL,
                    last_login       TEXT
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)"
            )
            conn.execute("""
                CREATE TABLE IF NOT EXISTS password_reset_tokens (
                    token       TEXT PRIMARY KEY,
                    user_id     TEXT NOT NULL,
                    expires_at  TEXT NOT NULL,
                    used        INTEGER NOT NULL DEFAULT 0,
                    created_at  TEXT NOT NULL
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_reset_tokens_user ON password_reset_tokens(user_id)"
            )
            conn.commit()

    # ── Password helpers ─────────────────────────────────────────────────────

    def hash_password(self, password: str) -> str:
        salt = secrets.token_hex(_SALT_BYTES)
        dk = hashlib.pbkdf2_hmac(
            _HASH_ALGO, password.encode(), salt.encode(), _ITERATIONS
        )
        return f"pbkdf2:{salt}:{dk.hex()}"

    def verify_password(self, password: str, stored_hash: str) -> bool:
        try:
            _, salt, dk_hex = stored_hash.split(":")
            dk = hashlib.pbkdf2_hmac(
                _HASH_ALGO, password.encode(), salt.encode(), _ITERATIONS
            )
            return secrets.compare_digest(dk.hex(), dk_hex)
        except Exception:
            return False

    # ── CRUD ─────────────────────────────────────────────────────────────────

    def create_user(self, email: str, password: str, role: str = "user") -> User:
        user_id = str(uuid.uuid4())
        hashed = self.hash_password(password)
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO users (id, email, hashed_password, role, is_active, created_at) "
                "VALUES (?, ?, ?, ?, 1, ?)",
                (user_id, email.lower().strip(), hashed, role, now),
            )
            conn.commit()
        return User(id=user_id, email=email, role=role, is_active=True, created_at=now)

    def get_by_email(self, email: str) -> Optional[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM users WHERE email = ?", (email.lower().strip(),)
            ).fetchone()
            return dict(row) if row else None

    def get_by_id(self, user_id: str) -> Optional[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM users WHERE id = ?", (user_id,)
            ).fetchone()
            return dict(row) if row else None

    def update_last_login(self, user_id: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE users SET last_login = ? WHERE id = ?",
                (datetime.utcnow().isoformat(), user_id),
            )
            conn.commit()

    def update_password(self, user_id: str, new_password: str) -> None:
        hashed = self.hash_password(new_password)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE users SET hashed_password = ? WHERE id = ?",
                (hashed, user_id),
            )
            conn.commit()

    def email_exists(self, email: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM users WHERE email = ?",
                (email.lower().strip(),),
            ).fetchone()[0]
            return count > 0

    def count_users(self) -> int:
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]

    # ── Password reset tokens ────────────────────────────────────────────────

    def create_reset_token(self, user_id: str, expire_minutes: int = 30) -> str:
        """Create a one-time password reset token, invalidating any previous
        unused tokens for this user."""
        from datetime import timedelta

        token = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc)
        expires_at = (now + timedelta(minutes=expire_minutes)).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE password_reset_tokens SET used = 1 WHERE user_id = ? AND used = 0",
                (user_id,),
            )
            conn.execute(
                "INSERT INTO password_reset_tokens (token, user_id, expires_at, used, created_at) "
                "VALUES (?, ?, ?, 0, ?)",
                (token, user_id, expires_at, now.isoformat()),
            )
            conn.commit()
        return token

    def get_valid_reset_token(self, token: str) -> Optional[dict]:
        """Return the token row if it exists, is unused, and hasn't expired."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM password_reset_tokens WHERE token = ?", (token,)
            ).fetchone()
        if not row:
            return None
        row = dict(row)
        if row["used"]:
            return None
        if datetime.fromisoformat(row["expires_at"]) < datetime.now(timezone.utc):
            return None
        return row

    def consume_reset_token(self, token: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE password_reset_tokens SET used = 1 WHERE token = ?", (token,)
            )
            conn.commit()
