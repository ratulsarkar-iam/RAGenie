import sqlite3
import json
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from pathlib import Path
from .models import Memory, MemoryType
from ..core.logging_config import get_logger

logger = get_logger(__name__)


class MemoryStore:
    """SQLite-based persistent storage for user memories."""

    def __init__(self, db_path: str = "data/memory/memories.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    last_accessed TEXT NOT NULL,
                    access_count INTEGER DEFAULT 0
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_profile (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS learning_progress (
                    topic TEXT PRIMARY KEY,
                    mastery_score REAL DEFAULT 0.0,
                    last_reviewed TEXT,
                    review_count INTEGER DEFAULT 0,
                    next_review TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_type ON memories(type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_accessed ON memories(last_accessed)")
            conn.commit()
        logger.debug(f"Memory database initialized at {self.db_path}")

    def store_memory(self, memory: Memory) -> str:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO memories
                (id, type, content, metadata, created_at, last_accessed, access_count)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                memory.id,
                memory.type.value,
                memory.content,
                json.dumps(memory.metadata),
                memory.created_at.isoformat(),
                memory.last_accessed.isoformat(),
                memory.access_count
            ))
            conn.commit()
        return memory.id

    @staticmethod
    def _escape_like(term: str) -> str:
        """Escape LIKE wildcards so user input is treated as a literal string."""
        return term.replace("!", "!!").replace("%", "!%").replace("_", "!_")

    def retrieve_memories(self, query: str, limit: int = 10) -> List[Memory]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if query:
                # Limit to 10 words max to prevent excessive queries
                words = [w for w in query.split() if len(w) > 2][:10]
                if not words:
                    words = [query[:100]]
                # Escape wildcards then wrap with %
                escaped = [f"%{self._escape_like(w)}%" for w in words]
                conditions = " OR ".join(["content LIKE ? ESCAPE '!'" for _ in escaped])
                params = escaped + [limit]
                cursor = conn.execute(f"""
                    SELECT * FROM memories
                    WHERE ({conditions}) OR type = 'preference'
                    ORDER BY access_count DESC, last_accessed DESC
                    LIMIT ?
                """, params)
            else:
                cursor = conn.execute("""
                    SELECT * FROM memories
                    ORDER BY access_count DESC, last_accessed DESC
                    LIMIT ?
                """, (limit,))

            memories = []
            for row in cursor.fetchall():
                memories.append(Memory(
                    id=row["id"],
                    type=MemoryType(row["type"]),
                    content=row["content"],
                    metadata=json.loads(row["metadata"] or "{}"),
                    created_at=datetime.fromisoformat(row["created_at"]),
                    last_accessed=datetime.fromisoformat(row["last_accessed"]),
                    access_count=row["access_count"] + 1  # reflect post-update value
                ))

            ids = [m.id for m in memories]
            if ids:
                placeholders = ",".join("?" * len(ids))
                conn.execute(f"""
                    UPDATE memories
                    SET access_count = access_count + 1,
                        last_accessed = ?
                    WHERE id IN ({placeholders})
                """, [datetime.now(timezone.utc).isoformat()] + ids)
                conn.commit()

            return memories

    def delete_memory(self, memory_id: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            conn.commit()
            return cursor.rowcount > 0

    def get_profile_value(self, key: str) -> Optional[str]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT value FROM user_profile WHERE key = ?", (key,))
            row = cursor.fetchone()
            return json.loads(row[0]) if row else None

    def set_profile_value(self, key: str, value) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO user_profile (key, value, updated_at)
                VALUES (?, ?, ?)
            """, (key, json.dumps(value), datetime.now(timezone.utc).isoformat()))
            conn.commit()

    def get_mastery(self, topic: str) -> float:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT mastery_score FROM learning_progress WHERE topic = ?", (topic,)
            )
            row = cursor.fetchone()
            return row[0] if row else 0.0

    def set_mastery(self, topic: str, mastery: float, next_review: Optional[datetime] = None) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO learning_progress (topic, mastery_score, last_reviewed, review_count, next_review)
                VALUES (?, ?, ?, 1, ?)
                ON CONFLICT(topic) DO UPDATE SET
                    mastery_score = excluded.mastery_score,
                    last_reviewed = excluded.last_reviewed,
                    review_count = review_count + 1,
                    next_review = excluded.next_review
            """, (
                topic,
                round(min(1.0, max(0.0, mastery)), 3),
                datetime.now(timezone.utc).isoformat(),
                next_review.isoformat() if next_review else None
            ))
            conn.commit()

    def get_all_learning_progress(self) -> List[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM learning_progress ORDER BY mastery_score ASC")
            return [dict(row) for row in cursor.fetchall()]
