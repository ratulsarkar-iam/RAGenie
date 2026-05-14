"""Unit tests for ArticleProcessor — uses temp SQLite, mocks RAG store."""
import pytest
from unittest.mock import MagicMock
from src.news.article_store import ArticleStore
from src.news.processor import ArticleProcessor
from src.news.models import RawArticle, Keyword, KeywordCreate


@pytest.fixture
def article_store(tmp_path):
    return ArticleStore(str(tmp_path / "articles.db"))


@pytest.fixture
def keyword():
    return Keyword(
        id="kw-1",
        term="West Bengal",
        enabled=True,
        fetch_interval_minutes=60,
        max_articles_per_fetch=10,
    )


def _raw(title: str = "West Bengal Election Result",
         content: str = "West Bengal election results are out.",
         url: str = "https://example.com/article-1") -> RawArticle:
    return RawArticle(title=title, content=content, url=url, source="TestSource")


class TestArticleProcessor:
    def test_accepts_relevant_article(self, article_store, keyword):
        proc = ArticleProcessor(article_store)
        result = proc.process([_raw()], keyword)
        assert result.accepted == 1
        assert result.irrelevant == 0
        assert result.duplicate == 0

    def test_deduplicates_same_url(self, article_store, keyword):
        proc = ArticleProcessor(article_store)
        raw = _raw()
        proc.process([raw], keyword)
        result = proc.process([raw], keyword)
        assert result.duplicate == 1
        assert result.accepted == 0

    def test_filters_irrelevant_article(self, article_store, keyword):
        proc = ArticleProcessor(article_store)
        raw = _raw(title="Swimming pool construction", content="Building pools in London.")
        result = proc.process([raw], keyword)
        assert result.irrelevant == 1
        assert result.accepted == 0

    def test_filters_empty_content(self, article_store, keyword):
        proc = ArticleProcessor(article_store)
        raw = _raw(content="short")
        result = proc.process([raw], keyword)
        assert result.invalid == 1

    def test_truncates_long_content(self, article_store, keyword):
        proc = ArticleProcessor(article_store, max_content_chars=50)
        raw = _raw(content="West Bengal " + "X" * 1000)
        proc.process([raw], keyword)
        saved = article_store.get(
            __import__("hashlib").sha256("https://example.com/article-1".encode()).hexdigest()
        )
        assert len(saved.content) <= 50

    def test_rag_ingestion_called_when_enabled(self, article_store, keyword):
        rag = MagicMock()
        rag.ingest_text = MagicMock(return_value="doc-id-1")
        proc = ArticleProcessor(article_store, rag_store=rag, max_content_chars=8000, ingest_into_rag=True)
        result = proc.process([_raw()], keyword)
        assert result.rag_ingested == 1
        rag.ingest_text.assert_called_once()

    def test_rag_ingestion_skipped_when_no_rag_store(self, article_store, keyword):
        proc = ArticleProcessor(article_store, rag_store=None)
        result = proc.process([_raw()], keyword)
        assert result.rag_ingested == 0
        assert result.accepted == 1

    def test_rag_ingestion_failure_does_not_block_save(self, article_store, keyword):
        rag = MagicMock()
        rag.ingest_text = MagicMock(side_effect=Exception("RAG down"))
        proc = ArticleProcessor(article_store, rag_store=rag)
        result = proc.process([_raw()], keyword)
        assert result.accepted == 1
        assert result.errors == 0

    def test_process_result_counts_mixed_batch(self, article_store, keyword):
        proc = ArticleProcessor(article_store)
        articles = [
            _raw(url="https://example.com/1"),
            _raw(title="Pools", content="Swimming pools", url="https://example.com/2"),
            _raw(content="x", url="https://example.com/3"),
        ]
        result = proc.process(articles, keyword)
        assert result.accepted == 1
        assert result.irrelevant == 1
        assert result.invalid == 1
