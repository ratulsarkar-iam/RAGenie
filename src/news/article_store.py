"""SQLite-backed article store for the News Aggregator."""
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

from ..core.logging_config import get_logger
from .models import Article, ArticleWithSummary

logger = get_logger(__name__)


@dataclass
class CleanupResult:
    deleted: int
    rag_purged: int
    errors: int
    rag_doc_ids: List[str] = field(default_factory=list)


class ArticleStore:
    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS articles (
                    id              TEXT PRIMARY KEY,
                    keyword_id      TEXT NOT NULL,
                    title           TEXT NOT NULL,
                    content         TEXT NOT NULL,
                    url             TEXT NOT NULL UNIQUE,
                    source          TEXT,
                    published_at    TEXT,
                    fetched_at      TEXT NOT NULL,
                    is_summarised   INTEGER NOT NULL DEFAULT 0,
                    rag_doc_id      TEXT,
                    image_url       TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS article_summaries (
                    article_id      TEXT PRIMARY KEY,
                    summary         TEXT NOT NULL,
                    model           TEXT NOT NULL,
                    generated_at    TEXT NOT NULL,
                    FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE
                )
            """)
            # Migrate existing databases that pre-date the image_url column
            existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(articles)").fetchall()}
            if "image_url" not in existing_cols:
                conn.execute("ALTER TABLE articles ADD COLUMN image_url TEXT")
            conn.commit()

    def _row_to_article(self, row: tuple) -> Article:
        return Article(
            id=row[0], keyword_id=row[1], title=row[2], content=row[3],
            url=row[4], source=row[5] or "",
            published_at=datetime.fromisoformat(row[6]) if row[6] else None,
            fetched_at=datetime.fromisoformat(row[7]),
            is_summarised=bool(row[8]), rag_doc_id=row[9],
            image_url=row[10] if len(row) > 10 else None,
        )

    def save(self, article: Article) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.execute(
                    "INSERT OR IGNORE INTO articles "
                    "(id,keyword_id,title,content,url,source,published_at,fetched_at,is_summarised,rag_doc_id,image_url) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (article.id, article.keyword_id, article.title, article.content,
                     article.url, article.source,
                     article.published_at.isoformat() if article.published_at else None,
                     article.fetched_at.isoformat(), int(article.is_summarised), article.rag_doc_id,
                     article.image_url),
                )
                conn.commit()
            return cur.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to save article {article.id}: {e}")
            return False

    def get(self, article_id: str) -> Optional[Article]:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT * FROM articles WHERE id=?", (article_id,)).fetchone()
        return self._row_to_article(row) if row else None

    def list_by_keyword(
        self,
        keyword_id: Optional[str],
        page: int = 1,
        limit: int = 20,
        summarised_only: bool = False,
    ) -> List[ArticleWithSummary]:
        offset = (page - 1) * limit
        where_parts = []
        params = []
        if keyword_id:
            where_parts.append("a.keyword_id = ?")
            params.append(keyword_id)
        if summarised_only:
            where_parts.append("a.is_summarised = 1")
        where_sql = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""
        params.extend([limit, offset])
        sql = (
            "SELECT a.*, s.summary, s.model FROM articles a "
            "LEFT JOIN article_summaries s ON s.article_id = a.id "
            f"{where_sql} ORDER BY a.fetched_at DESC LIMIT ? OFFSET ?"
        )
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(sql, params).fetchall()
        result = []
        for row in rows:
            article = self._row_to_article(row[:11])
            result.append(ArticleWithSummary(
                id=article.id, keyword_id=article.keyword_id,
                title=article.title, content=article.content,
                url=article.url, source=article.source,
                published_at=article.published_at, fetched_at=article.fetched_at,
                is_summarised=article.is_summarised, rag_doc_id=article.rag_doc_id,
                image_url=article.image_url,
                summary=row[11], summary_model=row[12],
            ))
        return result

    def list_pending_summarisation(self, limit: int = 50) -> List[Article]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM articles WHERE is_summarised=0 LIMIT ?", (limit,)
            ).fetchall()
        return [self._row_to_article(r) for r in rows]

    def save_summary(self, article_id: str, summary: str, model: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO article_summaries (article_id,summary,model,generated_at) VALUES (?,?,?,?)",
                (article_id, summary, model, now),
            )
            conn.execute("UPDATE articles SET is_summarised=1 WHERE id=?", (article_id,))
            conn.commit()

    def update_rag_doc_id(self, article_id: str, rag_doc_id: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE articles SET rag_doc_id=? WHERE id=?", (rag_doc_id, article_id))
            conn.commit()

    def delete(self, article_id: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("DELETE FROM articles WHERE id=?", (article_id,))
            conn.commit()
        return cur.rowcount > 0

    def count_by_keyword(self, keyword_id: str) -> int:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM articles WHERE keyword_id=?", (keyword_id,)
            ).fetchone()
        return row[0] if row else 0

    def delete_older_than(self, days: int) -> CleanupResult:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA foreign_keys = ON")
                rows = conn.execute(
                    "SELECT rag_doc_id FROM articles WHERE fetched_at < ? AND rag_doc_id IS NOT NULL",
                    (cutoff,),
                ).fetchall()
                rag_ids = [r[0] for r in rows]
                cur = conn.execute("DELETE FROM articles WHERE fetched_at < ?", (cutoff,))
                conn.commit()
            logger.info(f"Retention cleanup: removed {cur.rowcount} articles older than {days} days")
            return CleanupResult(deleted=cur.rowcount, rag_purged=len(rag_ids), errors=0, rag_doc_ids=rag_ids)
        except Exception as e:
            logger.error(f"Retention cleanup failed: {e}")
            return CleanupResult(deleted=0, rag_purged=0, errors=1)
