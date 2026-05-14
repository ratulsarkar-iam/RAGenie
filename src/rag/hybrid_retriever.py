from typing import List, Optional
from dataclasses import dataclass, field
from .page_index_store import PageIndexStore
from .document_classifier import DocumentClassifier, SearchMethod
from ..core.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class SearchResult:
    id: str
    content: str
    score: float
    source: str = ""
    metadata: dict = field(default_factory=dict)
    search_method: str = "bm25"


class HybridRetriever:
    """Combines BM25 (PageIndexStore) and optional vector search."""

    def __init__(
        self,
        page_index_store: PageIndexStore,
        vector_store=None,
        embedding_manager=None,
        classifier: Optional[DocumentClassifier] = None,
        bm25_weight: float = 0.6,
        vector_weight: float = 0.4,
        alpha: float = None,  # alpha is synonym for vector_weight
    ):
        self.page_index_store = page_index_store
        self.bm25_store = page_index_store  # alias
        self.vector_store = vector_store
        self.embedding_manager = embedding_manager
        self.classifier = classifier or DocumentClassifier()
        if alpha is not None:
            self.vector_weight = alpha
            self.bm25_weight = 1.0 - alpha
        else:
            self.bm25_weight = bm25_weight
            self.vector_weight = vector_weight

    def search(self, query: str, top_k: int = 5) -> List[SearchResult]:
        if self.vector_store:
            return self._hybrid_search(query, top_k)
        return self._bm25_search(query, top_k)

    def _bm25_search(self, query: str, top_k: int, fetch_k: int = None) -> List[SearchResult]:
        k = fetch_k or top_k
        chunks = self.page_index_store.search_chunks(query, top_k=k)
        return [
            SearchResult(
                id=getattr(c, "chunk_id", getattr(c, "id", str(i))),
                content=c.content,
                score=1.0 - (i * 0.1),
                source=getattr(c, "source", ""),
                search_method="bm25"
            )
            for i, c in enumerate(chunks)
        ]

    def _hybrid_search(self, query: str, top_k: int) -> List[SearchResult]:
        fetch_k = top_k * 2
        bm25_results = self._bm25_search(query, top_k, fetch_k=fetch_k)

        try:
            vector_results = self.vector_store.search(query, top_k=fetch_k)
        except Exception as e:
            logger.warning(f"Vector search failed, falling back to BM25: {e}")
            return bm25_results[:top_k]

        # Merge and re-score (deduplicate by id)
        merged: dict = {}
        for r in bm25_results:
            merged[r.id] = SearchResult(
                id=r.id, content=r.content,
                score=r.score * self.bm25_weight,
                source=r.source, search_method="hybrid"
            )

        for vr in vector_results:
            vid = getattr(vr, "id", str(id(vr)))
            meta = getattr(vr, "metadata", {}) or {}
            if vid in merged:
                merged[vid].score += getattr(vr, "score", 0.0) * self.vector_weight
            else:
                merged[vid] = SearchResult(
                    id=vid, content=getattr(vr, "content", ""),
                    score=getattr(vr, "score", 0.0) * self.vector_weight,
                    source=meta.get("source", ""),
                    metadata=meta,
                    search_method="vector"
                )

        return sorted(merged.values(), key=lambda r: r.score, reverse=True)[:top_k]

    def calculate_hybrid_score(self, bm25_score: float, semantic_score: float, alpha: float = None) -> float:
        """Compute weighted hybrid score. alpha = BM25 weight (1.0 = all BM25, 0.0 = all semantic)."""
        bw = alpha if alpha is not None else self.bm25_weight
        vw = 1.0 - bw
        return bm25_score * bw + semantic_score * vw
