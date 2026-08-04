"""SQLite-backed store for voice command history.

Retention is enforced on every insert: rows older than `retention_days` are
deleted, so the table always holds at most that many days of history.
"""
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

from ..core.logging_config import get_logger

logger = get_logger(__name__)


class VoiceCommandStore:
    def __init__(self, db_path: str = "data/voice/commands.db", retention_days: int = 3):
        self.db_path = db_path
        self.retention_days = retention_days
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS voice_commands (
                    id            TEXT PRIMARY KEY,
                    user_id       TEXT NOT NULL,
                    command_text  TEXT NOT NULL,
                    response_text TEXT,
                    created_at    TEXT NOT NULL
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_voice_commands_user_created "
                "ON voice_commands(user_id, created_at DESC)"
            )
            conn.commit()

    def add(self, user_id: str, command_text: str, response_text: Optional[str] = None) -> None:
        """Record a voice command and prune anything past the retention window."""
        try:
            now = datetime.now(timezone.utc)
            cutoff = (now - timedelta(days=self.retention_days)).isoformat()
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT INTO voice_commands (id, user_id, command_text, response_text, created_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (str(uuid.uuid4()), user_id, command_text[:2000],
                     (response_text or "")[:4000], now.isoformat()),
                )
                conn.execute("DELETE FROM voice_commands WHERE created_at < ?", (cutoff,))
                conn.commit()
        except Exception as e:
            logger.warning(f"Failed to record voice command: {e}")

    def list_for_user(self, user_id: str, limit: int = 100) -> List[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM voice_commands WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]
