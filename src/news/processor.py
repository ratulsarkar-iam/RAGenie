"""Article processor — dedup, relevance filter, persist, optional RAG ingestion."""
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

from ..core.logging_config import get_logger
from .models import Article, Keyword, RawArticle
from .article_store import ArticleStore

logger = get_logger(__name__)

_MIN_CONTENT_LEN = 10  # short for CJK/non-Latin languages


@dataclass
class ProcessResult:
    accepted: int = 0
    duplicate: int = 0
    irrelevant: int = 0
    invalid: int = 0
    rag_ingested: int = 0
    errors: int = 0


def _article_id(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()


def _is_relevant(raw: RawArticle, keyword_term: str) -> bool:
    """Language-agnostic relevance check.

    Splits keyword on whitespace and checks that at least one token appears
    in the title or content.  Minimum token length is 1 so that single-char
    CJK tokens and two-letter abbreviations (e.g. 'AI', '中') are not silently
    discarded.  DuckDuckGo already pre-filters by keyword, so this is a light
    post-filter against completely unrelated articles.
    """
    tokens = [t.lower() for t in keyword_term.split() if len(t) >= 1]
    if not tokens:
        return True
    haystack = (raw.title + " " + raw.content).lower()
    return any(tok in haystack for tok in tokens)


class ArticleProcessor:
    def __init__(
        self,
        article_store: ArticleStore,
        rag_store=None,
        max_content_chars: int = 8000,
        ingest_into_rag: bool = False,
    ):
        self._store = article_store
        self._rag = rag_store
        self._max_chars = max_content_chars
        self._ingest = ingest_into_rag

    def process(self, raw_articles: List[RawArticle], keyword: Keyword) -> ProcessResult:
        result = ProcessResult()
        for raw in raw_articles:
            try:
                if not raw.title or len(raw.content) < _MIN_CONTENT_LEN:
                    result.invalid += 1
                    continue
                if not _is_relevant(raw, keyword.term):
                    result.irrelevant += 1
                    continue
                content = raw.content[: self._max_chars]
                article = Article(
                    id=_article_id(raw.url),
                    keyword_id=keyword.id,
                    title=raw.title,
                    content=content,
                    url=raw.url,
                    source=raw.source,
                    published_at=raw.published_at,
                    fetched_at=datetime.now(timezone.utc),
                )
                saved = self._store.save(article)
                if not saved:
                    result.duplicate += 1
                    continue
                result.accepted += 1
                if self._ingest and self._rag is not None:
                    try:
                        doc_text = (
                            f"# {article.title}\n\n"
                            f"Source: {article.source}\n"
                            f"Date: {article.published_at}\n\n"
                            f"{article.content}"
                        )
                        doc_id = self._rag.ingest_text(
                            text=doc_text,
                            metadata={"source": article.url, "type": "news", "keyword_id": keyword.id},
                        )
                        self._store.update_rag_doc_id(article.id, doc_id)
                        result.rag_ingested += 1
                    except Exception as e:
                        logger.warning(f"RAG ingestion failed for {article.id}: {e}")
            except Exception as e:
                logger.error(f"Error processing article '{getattr(raw, 'url', '?')}': {e}")
                result.errors += 1
        return result
