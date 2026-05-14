from enum import Enum
from dataclasses import dataclass, field
from typing import Optional
from ..core.logging_config import get_logger

logger = get_logger(__name__)


class SearchMethod(str, Enum):
    BM25 = "bm25"
    BM25_ONLY = "bm25_only"
    HYBRID = "hybrid"
    VECTOR = "vector"


@dataclass
class Document:
    doc_id: str
    filename: str = ""
    file_type: str = ""
    content: str = ""
    source: str = ""
    chunks: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


RESEARCH_KEYWORDS = {
    'research', 'paper', 'study', 'analysis', 'thesis', 'journal', 'arxiv', 'preprint',
    'technical', 'reference', 'specification', 'whitepaper',
}
COMPLEX_CONTENT_THRESHOLD = 500  # chars per chunk to be considered complex
SIZE_THRESHOLD = 50_000  # total content characters


class DocumentClassifier:
    """Classifies documents to determine the best search method."""

    def classify_document(self, document: Document) -> str:
        # Use source if filename is empty
        path = document.filename or document.source or ""
        filename = path.split("/")[-1].lower()

        # Research/academic documents → hybrid
        if any(kw in filename for kw in RESEARCH_KEYWORDS):
            return SearchMethod.HYBRID.value

        # Check metadata file size
        file_size = (document.metadata or {}).get("file_size", 0)
        if file_size and file_size > 1_000_000:
            return SearchMethod.HYBRID.value

        # Large plain content → hybrid
        if len(document.content) > SIZE_THRESHOLD:
            return SearchMethod.HYBRID.value

        # Complex chunks content → hybrid
        if document.chunks:
            total_chunk_len = sum(len(getattr(c, 'content', '')) for c in document.chunks)
            if total_chunk_len > COMPLEX_CONTENT_THRESHOLD:
                return SearchMethod.HYBRID.value

        return SearchMethod.BM25_ONLY.value

    def classify_query(self, query: str) -> str:
        words = query.lower().split()
        if len(words) > 5:
            return SearchMethod.HYBRID.value
        conceptual_words = {"explain", "how", "why", "what", "compare", "difference", "similar"}
        if any(w in words for w in conceptual_words):
            return SearchMethod.HYBRID.value
        return SearchMethod.BM25.value
