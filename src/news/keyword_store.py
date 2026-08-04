"""SQLite-backed keyword store for the News Aggregator — scoped per user_id."""
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from ..core.logging_config import get_logger
from .models import Keyword, KeywordCreate, KeywordUpdate

logger = get_logger(__name__)

_UNOWNED = "__unowned__"  # sentinel user_id for legacy rows pending migration

# Explicit column list (rather than "k.*") — legacy DBs get `user_id` appended via
# ALTER TABLE, which puts it at the END of the physical column order, not where a
# fresh CREATE TABLE would place it. _row_to_keyword() relies on this exact order.
_KEYWORD_COLUMNS = (
    "k.id, k.user_id, k.term, k.term_lower, k.enabled, k.fetch_interval_minutes, "
    "k.max_articles_per_fetch, k.created_at, k.last_fetched_at, k.last_error"
)


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
                    user_id         TEXT NOT NULL DEFAULT '__unowned__',
                    term            TEXT NOT NULL,
                    term_lower      TEXT NOT NULL,
                    enabled         INTEGER NOT NULL DEFAULT 1,
                    fetch_interval_minutes INTEGER NOT NULL DEFAULT 60,
                    max_articles_per_fetch INTEGER NOT NULL DEFAULT 10,
                    created_at      TEXT NOT NULL,
                    last_fetched_at TEXT,
                    last_error      TEXT
                )
            """)
            # Legacy DBs: add user_id if missing (SQLite can't add UNIQUE after the fact —
            # uniqueness for (user_id, term_lower) is enforced at the application layer).
            existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(keywords)").fetchall()}
            if "user_id" not in existing_cols:
                conn.execute(f"ALTER TABLE keywords ADD COLUMN user_id TEXT NOT NULL DEFAULT '{_UNOWNED}'")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_keywords_user ON keywords(user_id)"
            )
            conn.commit()

    def _row_to_keyword(self, row: tuple, article_count: int = 0) -> Keyword:
        return Keyword(
            id=row[0],
            user_id=row[1],
            term=row[2],
            enabled=bool(row[4]),
            fetch_interval_minutes=row[5],
            max_articles_per_fetch=row[6],
            created_at=datetime.fromisoformat(row[7]),
            last_fetched_at=datetime.fromisoformat(row[8]) if row[8] else None,
            last_error=row[9],
            article_count=article_count,
        )

    def create(self, user_id: str, req: KeywordCreate) -> Keyword:
        if self.term_exists(user_id, req.term):
            raise ValueError(f"term already exists for this user: '{req.term}'")
        kw_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO keywords
                   (id, user_id, term, term_lower, enabled, fetch_interval_minutes,
                    max_articles_per_fetch, created_at)
                   VALUES (?,?,?,?,1,?,?,?)""",
                (kw_id, user_id, req.term.strip(), req.term.strip().lower(),
                 req.fetch_interval_minutes, req.max_articles_per_fetch, now),
            )
            conn.commit()
        return self.get(kw_id)

    def list_all(self, user_id: str) -> List[Keyword]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                f"SELECT {_KEYWORD_COLUMNS}, COUNT(a.id) AS cnt "
                "FROM keywords k "
                "LEFT JOIN articles a ON a.keyword_id = k.id "
                "WHERE k.user_id = ? "
                "GROUP BY k.id ORDER BY k.created_at DESC",
                (user_id,),
            ).fetchall()
        result = []
        for row in rows:
            kw = self._row_to_keyword(row[:10], article_count=row[10])
            result.append(kw)
        return result

    def list_all_cross_user(self) -> List[Keyword]:
        """Return every keyword across all users (scheduler-internal, not exposed via API)."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                f"SELECT {_KEYWORD_COLUMNS}, COUNT(a.id) AS cnt "
                "FROM keywords k "
                "LEFT JOIN articles a ON a.keyword_id = k.id "
                "GROUP BY k.id ORDER BY k.created_at DESC"
            ).fetchall()
        result = []
        for row in rows:
            kw = self._row_to_keyword(row[:10], article_count=row[10])
            result.append(kw)
        return result

    def get(self, keyword_id: str) -> Optional[Keyword]:
        """Returns the keyword regardless of owner — callers must check `user_id` themselves."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                f"SELECT {_KEYWORD_COLUMNS}, COUNT(a.id) AS cnt "
                "FROM keywords k "
                "LEFT JOIN articles a ON a.keyword_id = k.id "
                "WHERE k.id = ? GROUP BY k.id",
                (keyword_id,),
            ).fetchone()
        if not row:
            return None
        return self._row_to_keyword(row[:10], article_count=row[10])

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

    def term_exists(self, user_id: str, term: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT 1 FROM keywords WHERE user_id = ? AND term_lower = ?",
                (user_id, term.strip().lower()),
            ).fetchone()
        return row is not None

    def get_due(self) -> List[Keyword]:
        """Return enabled keywords whose next fetch time has passed (cross-user, scheduler-internal)."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                f"SELECT {_KEYWORD_COLUMNS}, COUNT(a.id) AS cnt "
                "FROM keywords k "
                "LEFT JOIN articles a ON a.keyword_id = k.id "
                "WHERE k.enabled = 1 "
                "GROUP BY k.id",
                (),
            ).fetchall()
        now = datetime.now(timezone.utc)
        due = []
        for row in rows:
            kw = self._row_to_keyword(row[:10], article_count=row[10])
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

    def migrate_unowned_to(self, user_id: str) -> int:
        """Backfill legacy rows (created before multi-user support) to the given user_id."""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "UPDATE keywords SET user_id = ? WHERE user_id = ? OR user_id IS NULL",
                (user_id, _UNOWNED),
            )
            conn.commit()
        return cur.rowcount
