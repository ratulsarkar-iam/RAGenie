"""NewsService — facade that orchestrates fetch → process → summarise → cleanup."""
from datetime import datetime
from typing import List, Optional, TYPE_CHECKING

from ..core.logging_config import get_logger
from .article_store import ArticleStore, CleanupResult
from .keyword_store import KeywordStore
from .models import ArticleWithSummary, Keyword, KeywordCreate, KeywordUpdate
from .fetcher import NewsFetcher
from .processor import ArticleProcessor
from .summariser import Summariser
from .scheduler import NewsScheduler

if TYPE_CHECKING:
    from ..llm.langchain_wrapper import LangChainLLM

logger = get_logger(__name__)


class NewsService:
    def __init__(
        self,
        keyword_store: KeywordStore,
        article_store: ArticleStore,
        fetcher: Optional[NewsFetcher],
        processor: ArticleProcessor,
        summariser: Summariser,
        scheduler: NewsScheduler,
        summarise_on_fetch: bool = True,
        retention_days: int = 3,
        rag_store=None,
    ):
        self._keywords = keyword_store
        self._articles = article_store
        self._fetcher = fetcher
        self._processor = processor
        self._summariser = summariser
        self._scheduler = scheduler
        self._summarise_on_fetch = summarise_on_fetch
        self._retention_days = retention_days
        self._rag = rag_store

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        keywords = self._keywords.list_all_cross_user()
        self._scheduler.refresh(keywords)
        self._scheduler.start()

    def stop(self) -> None:
        self._scheduler.stop()

    def run_startup_cleanup(self) -> CleanupResult:
        result = self._articles.delete_older_than(self._retention_days)
        self._purge_rag_ids(result.rag_doc_ids)
        logger.info(
            f"Startup retention: removed {result.deleted} articles "
            f"({result.rag_purged} RAG docs purged)"
        )
        return result

    # ------------------------------------------------------------------
    # Keyword management
    # ------------------------------------------------------------------

    def create_keyword(self, user_id: str, req: KeywordCreate) -> Keyword:
        kw = self._keywords.create(user_id, req)
        self._scheduler.register_keyword(kw)
        return kw

    def list_keywords(self, user_id: str) -> List[Keyword]:
        return self._keywords.list_all(user_id)

    def get_keyword(self, keyword_id: str) -> Optional[Keyword]:
        """Returns the keyword regardless of owner — callers must check `user_id` themselves."""
        return self._keywords.get(keyword_id)

    def update_keyword(self, keyword_id: str, patch: KeywordUpdate) -> Optional[Keyword]:
        kw = self._keywords.update(keyword_id, patch)
        if kw:
            if kw.enabled:
                self._scheduler.register_keyword(kw)
            else:
                self._scheduler.remove_keyword(keyword_id)
        return kw

    def delete_keyword(self, keyword_id: str) -> bool:
        self._scheduler.remove_keyword(keyword_id)
        return self._keywords.delete(keyword_id)

    def keyword_exists(self, user_id: str, term: str) -> bool:
        return self._keywords.term_exists(user_id, term)

    def migrate_unowned_keywords_to(self, user_id: str) -> int:
        return self._keywords.migrate_unowned_to(user_id)

    def suggest_keyword(self, description: str) -> dict:
        return self._summariser.suggest_keyword(description)

    # ------------------------------------------------------------------
    # Fetch pipeline
    # ------------------------------------------------------------------

    def run_for_keyword(self, keyword_id: str) -> None:
        kw = self._keywords.get(keyword_id)
        if not kw or not kw.enabled:
            return
        if self._fetcher is None:
            logger.warning("NewsFetcher not available (missing API key)")
            return
        try:
            from_date = kw.last_fetched_at
            raw = self._fetcher.fetch(
                keyword=kw.term,
                page_size=kw.max_articles_per_fetch,
                from_date=from_date,
            )
            result = self._processor.process(raw, kw)
            logger.info(
                f"Keyword '{kw.term}': accepted={result.accepted} "
                f"dup={result.duplicate} irrelevant={result.irrelevant}"
            )
            self._keywords.mark_fetched(keyword_id, error=None)
            if self._summarise_on_fetch and result.accepted > 0:
                self._summariser.summarise_pending(self._articles)
        except Exception as e:
            logger.error(f"Fetch pipeline failed for keyword '{kw.term}': {e}")
            self._keywords.mark_fetched(keyword_id, error=str(e))

    def fetch_now(self, keyword_id: str) -> None:
        self.run_for_keyword(keyword_id)

    def run_all(self) -> None:
        for kw in self._keywords.get_due():
            self.run_for_keyword(kw.id)

    # ------------------------------------------------------------------
    # Articles
    # ------------------------------------------------------------------

    def get_articles(
        self,
        keyword_id: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ) -> List[ArticleWithSummary]:
        return self._articles.list_by_keyword(keyword_id, page=page, limit=limit)

    def get_article(self, article_id: str):
        article = self._articles.get(article_id)
        if not article:
            return None
        rows = self._articles.list_by_keyword(article.keyword_id, page=1, limit=1000)
        for a in rows:
            if a.id == article_id:
                return a
        return None

    def resummarise(self, article_id: str) -> Optional[ArticleWithSummary]:
        article = self._articles.get(article_id)
        if not article:
            return None
        with __import__("sqlite3").connect(self._articles.db_path) as conn:
            conn.execute("UPDATE articles SET is_summarised=0 WHERE id=?", (article_id,))
            conn.commit()
        self._summariser.summarise_pending(self._articles, limit=1)
        return self.get_article(article_id)

    def delete_article(self, article_id: str) -> bool:
        article = self._articles.get(article_id)
        if article and article.rag_doc_id and self._rag:
            try:
                self._rag.delete_document(article.rag_doc_id)
            except Exception as e:
                logger.warning(f"RAG purge failed for {article.rag_doc_id}: {e}")
        return self._articles.delete(article_id)

    # ------------------------------------------------------------------
    # Retention (called by scheduler)
    # ------------------------------------------------------------------

    def _retention_cleanup(self) -> None:
        result = self._articles.delete_older_than(self._retention_days)
        self._purge_rag_ids(result.rag_doc_ids)

    def _purge_rag_ids(self, rag_doc_ids: List[str]) -> None:
        if not rag_doc_ids or self._rag is None:
            return
        for doc_id in rag_doc_ids:
            try:
                self._rag.delete_document(doc_id)
            except Exception as e:
                logger.warning(f"Failed to purge RAG doc {doc_id}: {e}")
