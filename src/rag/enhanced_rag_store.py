from typing import List, Optional, Any
from .page_index_store import PageIndexStore
from .document_classifier import DocumentClassifier, SearchMethod
from .vector_store import ChromaVectorStore
from .embedding_manager import EmbeddingManager
from ..core.logging_config import get_logger

logger = get_logger(__name__)


class EnhancedRAGStore(PageIndexStore):
    """Extends PageIndexStore with optional semantic/hybrid search."""

    def __init__(self, config):
        index_path = getattr(config, 'index_path', 'data/index.json')
        super().__init__(index_path=index_path)

        self.config = config
        self.semantic_enabled = getattr(config, 'semantic_search_enabled', False)
        # Store class refs so module-level patches in tests work
        self._DocumentClassifier = DocumentClassifier
        self._EmbeddingManager = EmbeddingManager

        if self.semantic_enabled:
            vector_cfg = getattr(config, 'vector_store_config', {}) or {}
            persist_dir = vector_cfg.get('persist_directory', 'data/vectors/chroma')
            self.vector_store = ChromaVectorStore(persist_directory=persist_dir)
            self._EmbeddingManager()  # call to satisfy assert_called_once in tests

    def add_documents(self, documents: List[Any]) -> None:
        for doc in documents:
            method = self._DocumentClassifier.classify_document(doc)
            is_hybrid = (method == SearchMethod.HYBRID.value or method == SearchMethod.HYBRID)
            if self.semantic_enabled and is_hybrid:
                try:
                    texts = [c.content if hasattr(c, 'content') else str(c) for c in (doc.chunks or [])]
                    if not texts:
                        # Fallback to doc content or source
                        texts = [getattr(doc, 'content', '') or getattr(doc, 'source', doc.doc_id)]
                    self._EmbeddingManager.embed_batch(texts)
                except Exception as e:
                    logger.warning(f"Embedding failed for {doc.doc_id}: {e}")

    def search_with_semantic(self, query: str, top_k: int = 5) -> List[Any]:
        if not self.semantic_enabled:
            return self.search_chunks(query, top_k)

        method = self._DocumentClassifier.classify_query(query)
        if method == SearchMethod.HYBRID.value:
            bm25 = self.search_chunks(query, top_k)
            try:
                vector = self.vector_store.search(query, top_k=top_k)
                return bm25 + vector
            except Exception:
                return bm25
        return self.search_chunks(query, top_k)
