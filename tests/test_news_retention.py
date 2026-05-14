"""Unit tests for ArticleStore retention (delete_older_than) — real temp SQLite."""
import hashlib
import sqlite3
from datetime import datetime, timedelta

import pytest

from src.news.article_store import ArticleStore
from src.news.models import Article


def _article_id(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()


def _insert_article(store: ArticleStore, url: str, fetched_at: datetime, rag_doc_id: str | None = None):
    """Directly insert an article with a controlled fetched_at timestamp."""
    art = Article(
        id=_article_id(url),
        keyword_id="kw-1",
        title="Test Title",
        content="Some content for testing retention.",
        url=url,
        source="TestSource",
        fetched_at=fetched_at,
        rag_doc_id=rag_doc_id,
    )
    with sqlite3.connect(store.db_path) as conn:
        conn.execute(
            """INSERT OR IGNORE INTO articles
               (id, keyword_id, title, content, url, source, published_at,
                fetched_at, is_summarised, rag_doc_id)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                art.id, art.keyword_id, art.title, art.content, art.url,
                art.source, None,
                art.fetched_at.isoformat(), 0, art.rag_doc_id,
            ),
        )
        conn.commit()
    return art


@pytest.fixture
def store(tmp_path):
    return ArticleStore(str(tmp_path / "articles.db"))


class TestRetentionCleanup:
    def test_empty_db_returns_zero(self, store):
        result = store.delete_older_than(3)
        assert result.deleted == 0
        assert result.rag_purged == 0

    def test_deletes_old_articles(self, store):
        old_date = datetime.utcnow() - timedelta(days=5)
        _insert_article(store, "https://example.com/old", old_date)
        result = store.delete_older_than(3)
        assert result.deleted == 1

    def test_keeps_recent_articles(self, store):
        recent = datetime.utcnow() - timedelta(hours=12)
        _insert_article(store, "https://example.com/recent", recent)
        result = store.delete_older_than(3)
        assert result.deleted == 0

    def test_mixed_batch(self, store):
        old = datetime.utcnow() - timedelta(days=10)
        new = datetime.utcnow() - timedelta(hours=1)
        _insert_article(store, "https://example.com/a", old)
        _insert_article(store, "https://example.com/b", old)
        _insert_article(store, "https://example.com/c", new)
        result = store.delete_older_than(3)
        assert result.deleted == 2

    def test_returns_rag_doc_ids_for_old_articles(self, store):
        old = datetime.utcnow() - timedelta(days=7)
        _insert_article(store, "https://example.com/rag1", old, rag_doc_id="doc-abc")
        _insert_article(store, "https://example.com/rag2", old, rag_doc_id="doc-xyz")
        result = store.delete_older_than(3)
        assert "doc-abc" in result.rag_doc_ids
        assert "doc-xyz" in result.rag_doc_ids
        assert result.rag_purged == 2

    def test_null_rag_doc_id_excluded_from_rag_list(self, store):
        old = datetime.utcnow() - timedelta(days=5)
        _insert_article(store, "https://example.com/no-rag", old, rag_doc_id=None)
        result = store.delete_older_than(3)
        assert result.deleted == 1
        assert result.rag_doc_ids == []

    def test_cascade_deletes_summaries(self, store):
        old = datetime.utcnow() - timedelta(days=5)
        art = _insert_article(store, "https://example.com/summ", old)
        with sqlite3.connect(store.db_path) as conn:
            conn.execute(
                "INSERT INTO article_summaries (article_id, summary, model, generated_at) VALUES (?,?,?,?)",
                (art.id, "A summary", "test-model", datetime.utcnow().isoformat()),
            )
            conn.commit()
        store.delete_older_than(3)
        with sqlite3.connect(store.db_path) as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM article_summaries WHERE article_id=?", (art.id,)
            ).fetchone()
        assert row[0] == 0

    def test_idempotent_double_call(self, store):
        old = datetime.utcnow() - timedelta(days=5)
        _insert_article(store, "https://example.com/once", old)
        store.delete_older_than(3)
        result2 = store.delete_older_than(3)
        assert result2.deleted == 0
