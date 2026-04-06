from abc import ABC, abstractmethod
from typing import List, Optional
from .models import Document


class DocumentStore(ABC):
    """Abstract interface for document storage backends.
    
    This interface allows swapping between different storage implementations
    (e.g., page-based indexing, vector databases) without changing retrieval logic.
    """
    
    @abstractmethod
    def add_documents(self, documents: List[Document]) -> None:
        """Add documents to the store.
        
        Args:
            documents: List of Document objects to add
        """
        pass
    
    @abstractmethod
    def search(self, query: str, top_k: int = 3) -> List[Document]:
        """Search for relevant documents based on query.
        
        Args:
            query: Search query string
            top_k: Number of top results to return
            
        Returns:
            List of most relevant Document objects
        """
        pass
    
    @abstractmethod
    def get_document(self, doc_id: str) -> Optional[Document]:
        """Retrieve a specific document by ID.
        
        Args:
            doc_id: Document identifier
            
        Returns:
            Document object if found, None otherwise
        """
        pass
    
    @abstractmethod
    def delete_document(self, doc_id: str) -> bool:
        """Delete a document from the store.
        
        Args:
            doc_id: Document identifier
            
        Returns:
            True if deleted, False if not found
        """
        pass
    
    @abstractmethod
    def delete_all(self) -> None:
        """Delete all documents from the store."""
        pass
    
    @abstractmethod
    def list_documents(self) -> List[Document]:
        """List all documents in the store.
        
        Returns:
            List of all Document objects
        """
        pass
    
    @abstractmethod
    def save(self) -> None:
        """Persist the store to disk."""
        pass
    
    @abstractmethod
    def load(self) -> None:
        """Load the store from disk."""
        pass
