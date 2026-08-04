"""SQLite-backed persistence for the per-user activity log."""
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from .models import ActivityEvent
from ..core.logging_config import get_logger

logger = get_logger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_event(row: sqlite3.Row) -> ActivityEvent:
    return ActivityEvent(
        id=row["id"],
        user_id=row["user_id"],
        event_type=row["event_type"],
        description=row["description"],
        metadata=json.loads(row["metadata"]) if row["metadata"] else None,
        created_at=datetime.fromisoformat(row["created_at"]),
    )


class ActivityStore:
    """CRUD store for activity log events, backed by SQLite."""

    def __init__(self, db_path: str = "data/activity/activity.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS activity_log (
                    id          TEXT PRIMARY KEY,
                    user_id     TEXT NOT NULL,
                    event_type  TEXT NOT NULL,
                    description TEXT NOT NULL,
                    metadata    TEXT,
                    created_at  TEXT NOT NULL
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_activity_user_created "
                "ON activity_log(user_id, created_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_activity_event_type ON activity_log(event_type)"
            )
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def log(
        self,
        user_id: str,
        event_type: str,
        description: str,
        metadata: Optional[dict] = None,
    ) -> ActivityEvent:
        event_id = str(uuid.uuid4())
        now = _now()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO activity_log (id, user_id, event_type, description, metadata, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    event_id, user_id, event_type, description,
                    json.dumps(metadata) if metadata is not None else None,
                    now,
                ),
            )
            conn.commit()
        return ActivityEvent(
            id=event_id, user_id=user_id, event_type=event_type,
            description=description, metadata=metadata,
            created_at=datetime.fromisoformat(now),
        )

    def list_for_user(
        self,
        user_id: str,
        event_type: Optional[str] = None,
        page: int = 1,
        limit: int = 50,
    ) -> List[ActivityEvent]:
        offset = (page - 1) * limit
        with self._connect() as conn:
            if event_type:
                rows = conn.execute(
                    "SELECT * FROM activity_log WHERE user_id = ? AND event_type = ? "
                    "ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    (user_id, event_type, limit, offset),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM activity_log WHERE user_id = ? "
                    "ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    (user_id, limit, offset),
                ).fetchall()
        return [_row_to_event(r) for r in rows]

    def list_all(
        self,
        user_id: Optional[str] = None,
        event_type: Optional[str] = None,
        page: int = 1,
        limit: int = 50,
    ) -> List[ActivityEvent]:
        offset = (page - 1) * limit
        clauses = []
        params: list = []
        if user_id:
            clauses.append("user_id = ?")
            params.append(user_id)
        if event_type:
            clauses.append("event_type = ?")
            params.append(event_type)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.extend([limit, offset])
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM activity_log {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                params,
            ).fetchall()
        return [_row_to_event(r) for r in rows]

    def count_for_user(self, user_id: str, event_type: Optional[str] = None) -> int:
        with self._connect() as conn:
            if event_type:
                row = conn.execute(
                    "SELECT COUNT(*) AS c FROM activity_log WHERE user_id = ? AND event_type = ?",
                    (user_id, event_type),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT COUNT(*) AS c FROM activity_log WHERE user_id = ?",
                    (user_id,),
                ).fetchone()
        return row["c"] if row else 0

    def count_all(self, user_id: Optional[str] = None, event_type: Optional[str] = None) -> int:
        clauses = []
        params: list = []
        if user_id:
            clauses.append("user_id = ?")
            params.append(user_id)
        if event_type:
            clauses.append("event_type = ?")
            params.append(event_type)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as conn:
            row = conn.execute(f"SELECT COUNT(*) AS c FROM activity_log {where}", params).fetchone()
        return row["c"] if row else 0
