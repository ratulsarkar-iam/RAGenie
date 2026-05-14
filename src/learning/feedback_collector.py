import sqlite3
import json
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum
from pathlib import Path
from ..core.logging_config import get_logger

logger = get_logger(__name__)


class FeedbackType(str, Enum):
    EXPLICIT = "explicit"
    IMPLICIT = "implicit"
    CORRECTION = "correction"


class Feedback:
    def __init__(self, type: str, message_id: str = "", rating: str = "",
                 comment: str = "", metrics: Optional[Dict] = None,
                 original_response: str = "", corrected_response: str = "",
                 metadata: Optional[Dict] = None,
                 timestamp: Optional[datetime] = None):
        self.id = str(uuid.uuid4())
        self.type = type
        self.message_id = message_id
        self.rating = rating
        self.comment = comment
        self.metrics = metrics or {}
        self.original_response = original_response
        self.corrected_response = corrected_response
        self.metadata = metadata or {}
        self.timestamp = timestamp or datetime.utcnow()

    @property
    def positive(self) -> bool:
        return self.rating == "thumbs_up"


class _FeedbackProcessor:
    """Simple processor object with a process method."""
    def __init__(self, feedback_type: str):
        self.feedback_type = feedback_type

    def process(self, feedback) -> None:
        pass


class FeedbackCollector:
    """Collects and persists user feedback."""

    def __init__(self, storage=None):
        # storage can be: None, a path string, a MemoryStore, or an abstract storage delegate
        if storage is None:
            storage = "data/memory/memories.db"

        if isinstance(storage, str):
            self.db_path: Optional[str] = storage
            self._storage_delegate = None
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
            self._init_db()
        elif hasattr(storage, 'db_path') and isinstance(getattr(storage, 'db_path', None), str):
            # MemoryStore passed directly
            self.db_path = storage.db_path
            self._storage_delegate = None
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
            self._init_db()
        else:
            # Abstract storage delegate (e.g. Mock in tests)
            self.db_path = None
            self._storage_delegate = storage

        # Processor registry keyed by feedback type (each entry has .process method)
        self.processors = {
            "explicit": _FeedbackProcessor("explicit"),
            "implicit": _FeedbackProcessor("implicit"),
            "correction": _FeedbackProcessor("correction"),
        }

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS feedback (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    message_id TEXT,
                    rating TEXT,
                    comment TEXT,
                    metrics TEXT DEFAULT '{}',
                    original_response TEXT,
                    corrected_response TEXT,
                    metadata TEXT DEFAULT '{}',
                    timestamp TEXT NOT NULL
                )
            """)
            conn.commit()

    async def collect_feedback(self, feedback_type: str, data: Dict[str, Any]) -> Feedback:
        feedback = Feedback(
            type=feedback_type,
            message_id=data.get("message_id", ""),
            rating=data.get("rating", ""),
            comment=data.get("comment", ""),
            metrics=data.get("metrics", {}),
            original_response=data.get("original_response", ""),
            corrected_response=data.get("corrected_response", ""),
            metadata=data.get("metadata", {})
        )

        if self._storage_delegate is not None:
            await self._storage_delegate.store(feedback)
            return feedback

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO feedback
                (id, type, message_id, rating, comment, metrics, original_response,
                 corrected_response, metadata, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                feedback.id, feedback.type, feedback.message_id, feedback.rating,
                feedback.comment, json.dumps(feedback.metrics), feedback.original_response,
                feedback.corrected_response, json.dumps(feedback.metadata),
                feedback.timestamp.isoformat()
            ))
            conn.commit()

        logger.debug(f"Feedback collected: {feedback_type} for message {feedback.message_id}")
        return feedback

    def get_recent_feedback(self, limit: int = 50) -> List[Feedback]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM feedback ORDER BY timestamp DESC LIMIT ?", (limit,)
            )
            results = []
            for row in cursor.fetchall():
                f = Feedback(
                    type=row["type"],
                    message_id=row["message_id"],
                    rating=row["rating"],
                    comment=row["comment"],
                    metrics=json.loads(row["metrics"] or "{}"),
                    original_response=row["original_response"],
                    corrected_response=row["corrected_response"],
                    metadata=json.loads(row["metadata"] or "{}")
                )
                f.id = row["id"]
                f.timestamp = datetime.fromisoformat(row["timestamp"])
                results.append(f)
            return results

    def get_stats(self) -> Dict[str, Any]:
        with sqlite3.connect(self.db_path) as conn:
            total = conn.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]
            positive = conn.execute(
                "SELECT COUNT(*) FROM feedback WHERE rating = 'thumbs_up'"
            ).fetchone()[0]
            return {
                "total": total,
                "positive": positive,
                "negative": total - positive,
                "satisfaction_rate": round(positive / total, 2) if total > 0 else 0.0
            }
