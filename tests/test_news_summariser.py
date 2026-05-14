"""Unit tests for Summariser — mocks LangChainLLM."""
import hashlib
import sqlite3
from datetime import datetime

import pytest
from unittest.mock import MagicMock, patch

from src.news.article_store import ArticleStore
from src.news.summariser import Summariser
from src.news.models import Article


def _article_id(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()


def _insert_article(store: ArticleStore, url: str = "https://example.com/a1", summarised: bool = False):
    art = Article(
        id=_article_id(url),
        keyword_id="kw-1",
        title="Test Article",
        content="This is a long enough article body for summarisation testing purposes.",
        url=url,
        source="TestSource",
        fetched_at=datetime.utcnow(),
        is_summarised=summarised,
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
                art.fetched_at.isoformat(), int(art.is_summarised), None,
            ),
        )
        conn.commit()
    return art


@pytest.fixture
def article_store(tmp_path):
    return ArticleStore(str(tmp_path / "art.db"))


@pytest.fixture
def llm():
    mock = MagicMock()
    mock.config = MagicMock()
    mock.config.model_name = "test-llm"
    mock.generate = MagicMock(return_value="A concise summary.")
    return mock


class TestSummariser:
    def test_summarise_returns_clean_string(self, llm):
        s = Summariser(llm)
        art = Article(
            id="abc", keyword_id="kw", title="T", content="Some content",
            url="https://x.com", source="S", fetched_at=datetime.utcnow(),
        )
        result = s.summarise(art)
        assert result == "A concise summary."

    def test_summarise_retries_on_exception(self, llm):
        llm.generate.side_effect = [Exception("LLM error"), "Retry summary."]
        s = Summariser(llm)
        art = Article(
            id="abc", keyword_id="kw", title="T", content="Content",
            url="https://x.com", source="S", fetched_at=datetime.utcnow(),
        )
        result = s.summarise(art)
        assert result == "Retry summary."
        assert llm.generate.call_count == 2

    def test_summarise_returns_fallback_after_two_failures(self, llm):
        llm.generate.side_effect = Exception("always fails")
        s = Summariser(llm)
        art = Article(
            id="abc", keyword_id="kw", title="T", content="Content",
            url="https://x.com", source="S", fetched_at=datetime.utcnow(),
        )
        result = s.summarise(art)
        assert result == "[Summary unavailable]"

    def test_summarise_treats_whitespace_only_as_failure(self, llm):
        llm.generate.side_effect = ["   ", "Real summary."]
        s = Summariser(llm)
        art = Article(
            id="abc", keyword_id="kw", title="T", content="Content",
            url="https://x.com", source="S", fetched_at=datetime.utcnow(),
        )
        result = s.summarise(art)
        assert result == "Real summary."

    def test_summarise_pending_processes_all(self, article_store, llm):
        _insert_article(article_store, "https://a.com/1")
        _insert_article(article_store, "https://a.com/2")
        s = Summariser(llm)
        result = s.summarise_pending(article_store)
        assert result.succeeded == 2
        assert result.failed == 0

    def test_summarise_pending_skips_already_summarised(self, article_store, llm):
        _insert_article(article_store, "https://a.com/1", summarised=True)
        _insert_article(article_store, "https://a.com/2", summarised=False)
        s = Summariser(llm)
        result = s.summarise_pending(article_store)
        assert result.succeeded == 1

    def test_summarise_pending_stores_fallback_on_failure(self, article_store, llm):
        llm.generate.side_effect = Exception("LLM down")
        _insert_article(article_store, "https://a.com/1")
        s = Summariser(llm)
        result = s.summarise_pending(article_store)
        assert result.failed == 1
        art_id = _article_id("https://a.com/1")
        with sqlite3.connect(article_store.db_path) as conn:
            row = conn.execute(
                "SELECT summary FROM article_summaries WHERE article_id=?", (art_id,)
            ).fetchone()
        assert row is not None
        assert row[0] == "[Summary unavailable]"

    def test_summarise_pending_respects_limit(self, article_store, llm):
        for i in range(5):
            _insert_article(article_store, f"https://a.com/{i}")
        s = Summariser(llm)
        result = s.summarise_pending(article_store, limit=2)
        assert result.succeeded == 2

    def test_model_name_stored_correctly(self, article_store, llm):
        llm.config.model_name = "deepseek-r1:1.5b"
        _insert_article(article_store, "https://a.com/m")
        s = Summariser(llm)
        s.summarise_pending(article_store)
        art_id = _article_id("https://a.com/m")
        with sqlite3.connect(article_store.db_path) as conn:
            row = conn.execute(
                "SELECT model FROM article_summaries WHERE article_id=?", (art_id,)
            ).fetchone()
        assert row[0] == "deepseek-r1:1.5b"
