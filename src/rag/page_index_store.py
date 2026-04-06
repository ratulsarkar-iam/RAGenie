import json
from pathlib import Path
from typing import List, Optional, Dict, Any
from rank_bm25 import BM25Okapi
from ..core.document_store import DocumentStore
from ..core.models import Document, Chunk
from ..core.logging_config import get_logger
from ..core.exceptions import DocumentStoreError, DocumentNotFoundError
from ..core.utils import ensure_directory

logger = get_logger(__name__)


class PageIndexStore(DocumentStore):
    """Page-based document store using BM25 for keyword search."""
    
    def __init__(self, index_path: str):
        self.index_path = Path(index_path)
        self.documents: Dict[str, Document] = {}
        self.chunks: List[Chunk] = []
        self.bm25: Optional[BM25Okapi] = None
        self._ensure_index_directory()
    
    def _ensure_index_directory(self):
        """Ensure the index directory exists."""
        ensure_directory(self.index_path.parent)
    
    def add_documents(self, documents: List[Document]) -> None:
        """Add documents to the store."""
        for doc in documents:
            # Store document
            self.documents[doc.doc_id] = doc
            
            # Add chunks to search index
            self.chunks.extend(doc.chunks)
        
        # Rebuild BM25 index
        self._rebuild_bm25_index()
        
        logger.info(f"Added {len(documents)} documents to store")
    
    def _rebuild_bm25_index(self):
        """Rebuild the BM25 index from all chunks."""
        if not self.chunks:
            self.bm25 = None
            return
        
        # Tokenize chunk contents for BM25
        tokenized_chunks = [chunk.content.lower().split() for chunk in self.chunks]
        self.bm25 = BM25Okapi(tokenized_chunks)
        
        logger.debug(f"Rebuilt BM25 index with {len(self.chunks)} chunks")
    
    def search(self, query: str, top_k: int = 3) -> List[Document]:
        """Search for relevant documents using BM25."""
        if not self.bm25 or not self.chunks:
            logger.warning("No documents in index")
            return []
        
        # Tokenize query
        tokenized_query = query.lower().split()
        
        # Get BM25 scores
        scores = self.bm25.get_scores(tokenized_query)
        
        # Get top-k chunk indices
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        
        # Get corresponding documents (deduplicate)
        doc_ids = []
        results = []
        for idx in top_indices:
            chunk = self.chunks[idx]
            if chunk.doc_id not in doc_ids:
                doc_ids.append(chunk.doc_id)
                if chunk.doc_id in self.documents:
                    results.append(self.documents[chunk.doc_id])
        
        logger.debug(f"Search for '{query}' returned {len(results)} documents")
        return results
    
    def search_chunks(self, query: str, top_k: int = 3) -> List[Chunk]:
        """Search for relevant chunks using BM25 with medical term expansion."""
        if not self.bm25 or not self.chunks:
            logger.warning("No chunks in index")
            return []
        
        # Expand medical terminology
        expanded_query = self._expand_medical_terms(query)
        
        # Tokenize query
        tokenized_query = expanded_query.lower().split()
        
        # Get BM25 scores
        scores = self.bm25.get_scores(tokenized_query)
        
        # Get top-k chunks
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        results = [self.chunks[idx] for idx in top_indices]
        
        logger.debug(f"Search for '{query}' (expanded: '{expanded_query}') returned {len(results)} chunks")
        return results
    
    def _expand_medical_terms(self, query: str) -> str:
        """Expand common medical terms to improve search recall."""
        query_lower = query.lower()
        
        # Medical term expansions
        expansions = {
            'vitals': 'vitals blood pressure heart rate temperature respiratory hemoglobin pulse oxygen saturation',
            'vital signs': 'blood pressure heart rate temperature respiratory hemoglobin pulse oxygen',
            'bp': 'blood pressure systolic diastolic',
            'sugar': 'glucose blood sugar diabetes hba1c glycosylated hemoglobin',
            'cholesterol': 'cholesterol ldl hdl triglycerides lipid profile',
            'liver': 'liver sgot sgpt ast alt bilirubin albumin alkaline phosphatase',
            'kidney': 'kidney creatinine urea bun uric acid sodium potassium',
            'cbc': 'complete blood count hemoglobin rbc wbc platelet hematocrit',
            'blood count': 'hemoglobin rbc wbc platelet hematocrit neutrophils lymphocytes',
        }
        
        # Check if query contains any medical terms and expand
        expanded = query
        for term, expansion in expansions.items():
            if term in query_lower:
                expanded = f"{query} {expansion}"
                break
        
        return expanded
    
    def get_document(self, doc_id: str) -> Optional[Document]:
        """Retrieve a specific document by ID."""
        return self.documents.get(doc_id)
    
    def delete_document(self, doc_id: str) -> bool:
        """Delete a document from the store."""
        if doc_id not in self.documents:
            return False
        
        # Remove document
        doc = self.documents.pop(doc_id)
        
        # Remove associated chunks
        self.chunks = [chunk for chunk in self.chunks if chunk.doc_id != doc_id]
        
        # Rebuild index
        self._rebuild_bm25_index()
        
        logger.info(f"Deleted document: {doc_id}")
        return True
    
    def delete_all(self) -> None:
        """Delete all documents from the store."""
        self.documents.clear()
        self.chunks.clear()
        self.bm25 = None
        logger.info("Deleted all documents from store")
    
    def list_documents(self) -> List[Document]:
        """List all documents in the store."""
        return list(self.documents.values())
    
    def save(self) -> None:
        """Persist the store to disk."""
        try:
            data = {
                "documents": {
                    doc_id: doc.dict() for doc_id, doc in self.documents.items()
                },
                "chunks": [chunk.dict() for chunk in self.chunks]
            }
            
            with open(self.index_path, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            
            logger.info(f"Saved index to {self.index_path}")
        except Exception as e:
            raise DocumentStoreError(f"Failed to save index: {str(e)}")
    
    def load(self) -> None:
        """Load the store from disk."""
        if not self.index_path.exists():
            logger.info("No existing index found, starting fresh")
            return
        
        try:
            with open(self.index_path, 'r') as f:
                data = json.load(f)
            
            # Load documents
            self.documents = {
                doc_id: Document(**doc_data)
                for doc_id, doc_data in data.get("documents", {}).items()
            }
            
            # Load chunks
            self.chunks = [Chunk(**chunk_data) for chunk_data in data.get("chunks", [])]
            
            # Rebuild BM25 index
            self._rebuild_bm25_index()
            
            logger.info(f"Loaded {len(self.documents)} documents from {self.index_path}")
        except Exception as e:
            raise DocumentStoreError(f"Failed to load index: {str(e)}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the store."""
        return {
            "num_documents": len(self.documents),
            "num_chunks": len(self.chunks),
            "index_path": str(self.index_path)
        }
