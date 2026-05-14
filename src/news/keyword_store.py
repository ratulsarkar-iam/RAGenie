"""SQLite-backed keyword store for the News Aggregator."""
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from ..core.logging_config import get_logger
from .models import Keyword, KeywordCreate, KeywordUpdate

logger = get_logger(__name__)


class KeywordStore:
    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS keywords (
                    id              TEXT PRIMARY KEY,
                    term            TEXT NOT NULL,
                    term_lower      TEXT NOT NULL UNIQUE,
                    enabled         INTEGER NOT NULL DEFAULT 1,
                    fetch_interval_minutes INTEGER NOT NULL DEFAULT 60,
                    max_articles_per_fetch INTEGER NOT NULL DEFAULT 10,
                    created_at      TEXT NOT NULL,
                    last_fetched_at TEXT,
                    last_error      TEXT
                )
            """)
            conn.commit()

    def _row_to_keyword(self, row: tuple, article_count: int = 0) -> Keyword:
        return Keyword(
            id=row[0],
            term=row[1],
            enabled=bool(row[3]),
            fetch_interval_minutes=row[4],
            max_articles_per_fetch=row[5],
            created_at=datetime.fromisoformat(row[6]),
            last_fetched_at=datetime.fromisoformat(row[7]) if row[7] else None,
            last_error=row[8],
            article_count=article_count,
        )

    def create(self, req: KeywordCreate) -> Keyword:
        kw_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO keywords
                   (id, term, term_lower, enabled, fetch_interval_minutes,
                    max_articles_per_fetch, created_at)
                   VALUES (?,?,?,1,?,?,?)""",
                (kw_id, req.term.strip(), req.term.strip().lower(),
                 req.fetch_interval_minutes, req.max_articles_per_fetch, now),
            )
            conn.commit()
        return self.get(kw_id)

    def list_all(self) -> List[Keyword]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT k.*, COUNT(a.id) AS cnt "
                "FROM keywords k "
                "LEFT JOIN articles a ON a.keyword_id = k.id "
                "GROUP BY k.id ORDER BY k.created_at DESC"
            ).fetchall()
        result = []
        for row in rows:
            kw = self._row_to_keyword(row[:9], article_count=row[9])
            result.append(kw)
        return result

    def get(self, keyword_id: str) -> Optional[Keyword]:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT k.*, COUNT(a.id) AS cnt "
                "FROM keywords k "
                "LEFT JOIN articles a ON a.keyword_id = k.id "
                "WHERE k.id = ? GROUP BY k.id",
                (keyword_id,),
            ).fetchone()
        if not row:
            return None
        return self._row_to_keyword(row[:9], article_count=row[9])

    def update(self, keyword_id: str, patch: KeywordUpdate) -> Optional[Keyword]:
        updates = {k: v for k, v in patch.model_dump().items() if v is not None}
        if not updates:
            return self.get(keyword_id)
        if "term" in updates:
            updates["term"] = updates["term"].strip()
            updates["term_lower"] = updates["term"].lower()
        cols = ", ".join(f"{k} = ?" for k in updates)
        vals = list(updates.values()) + [keyword_id]
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(f"UPDATE keywords SET {cols} WHERE id = ?", vals)
            conn.commit()
        return self.get(keyword_id)

    def delete(self, keyword_id: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("DELETE FROM keywords WHERE id = ?", (keyword_id,))
            conn.commit()
        return cur.rowcount > 0

    def term_exists(self, term: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT 1 FROM keywords WHERE term_lower = ?",
                (term.strip().lower(),),
            ).fetchone()
        return row is not None

    def get_due(self) -> List[Keyword]:
        """Return enabled keywords whose next fetch time has passed."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT k.*, COUNT(a.id) AS cnt "
                "FROM keywords k "
                "LEFT JOIN articles a ON a.keyword_id = k.id "
                "WHERE k.enabled = 1 "
                "GROUP BY k.id",
                (),
            ).fetchall()
        now = datetime.now(timezone.utc)
        due = []
        for row in rows:
            kw = self._row_to_keyword(row[:9], article_count=row[9])
            if kw.last_fetched_at is None:
                due.append(kw)
            else:
                elapsed = (now - kw.last_fetched_at).total_seconds() / 60
                if elapsed >= kw.fetch_interval_minutes:
                    due.append(kw)
        return due

    def mark_fetched(self, keyword_id: str, error: Optional[str] = None) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE keywords SET last_fetched_at = ?, last_error = ? WHERE id = ?",
                (now, error, keyword_id),
            )
            conn.commit()
