from typing import List, Optional
from dataclasses import dataclass, field
from ..core.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class Chunk:
    id: str
    doc_id: str
    content: str
    source: str = ""


@dataclass
class VectorResult:
    id: str
    content: str
    metadata: dict = field(default_factory=dict)
    score: float = 0.0


class ChromaVectorStore:
    """ChromaDB-based vector storage optimized for local use."""

    def __init__(self, persist_directory: str = "data/vectors/chroma"):
        self.persist_directory = persist_directory
        self._collection = None
        self._client = None

    @property
    def collection(self):
        """Public accessor — triggers lazy initialization."""
        return self._get_collection()

    def _get_collection(self):
        if self._collection is None:
            try:
                import chromadb
                from chromadb.config import Settings
                from pathlib import Path
                Path(self.persist_directory).mkdir(parents=True, exist_ok=True)
                self._client = chromadb.PersistentClient(
                    path=self.persist_directory,
                    settings=Settings(anonymized_telemetry=False, allow_reset=True)
                )
                self._collection = self._client.get_or_create_collection(
                    name="documents",
                    metadata={"hnsw:space": "cosine"}
                )
            except ImportError:
                logger.warning("chromadb not installed — vector store unavailable")
                raise
        return self._collection

    def add_embeddings(self, chunks: List[Chunk]) -> None:
        col = self._get_collection()
        col.add(
            documents=[c.content for c in chunks],
            metadatas=[{"doc_id": c.doc_id, "chunk_id": c.id, "source": c.source} for c in chunks],
            ids=[c.id for c in chunks]
        )

    def search(self, query: str, top_k: int = 5) -> List[VectorResult]:
        col = self._get_collection()
        results = col.query(query_texts=[query], n_results=top_k)
        return [
            VectorResult(
                id=results["ids"][0][i],
                content=results["documents"][0][i],
                metadata=results["metadatas"][0][i],
                score=1.0 - results["distances"][0][i]  # convert distance to score
            )
            for i in range(len(results["ids"][0]))
        ]

    def update_embeddings(self, chunk_id: str, embedding: List[float]) -> None:
        self._get_collection().update(ids=[chunk_id], embeddings=[embedding])

    def delete_embeddings(self, chunk_ids: List[str]) -> None:
        self._get_collection().delete(ids=chunk_ids)

    def get_stats(self) -> int:
        """Get collection count."""
        try:
            return self.collection.count()
        except Exception:
            return 0
