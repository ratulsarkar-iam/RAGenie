from langchain.schema import BaseRetriever, Document as LangChainDocument
from typing import List
from .page_index_store import PageIndexStore
from ..core.logging_config import get_logger

logger = get_logger(__name__)


class PageIndexRetriever(BaseRetriever):
    """LangChain retriever wrapper for PageIndexStore."""
    
    store: PageIndexStore
    top_k: int = 3
    
    class Config:
        arbitrary_types_allowed = True
    
    def _get_relevant_documents(self, query: str) -> List[LangChainDocument]:
        """Retrieve relevant documents for a query.
        
        Args:
            query: Search query
            
        Returns:
            List of LangChain Document objects
        """
        # Search for relevant chunks
        chunks = self.store.search_chunks(query, top_k=self.top_k)
        
        # Convert to LangChain documents
        langchain_docs = []
        for chunk in chunks:
            doc = LangChainDocument(
                page_content=chunk.content,
                metadata={
                    "chunk_id": chunk.chunk_id,
                    "doc_id": chunk.doc_id,
                    "source": chunk.metadata.get("source", ""),
                    "filename": chunk.metadata.get("filename", "")
                }
            )
            langchain_docs.append(doc)
        
        return langchain_docs
    
    async def _aget_relevant_documents(self, query: str) -> List[LangChainDocument]:
        """Async version of _get_relevant_documents."""
        return self._get_relevant_documents(query)


def create_retriever(store: PageIndexStore, top_k: int = 3) -> PageIndexRetriever:
    """Create a LangChain retriever from a PageIndexStore.
    
    Args:
        store: PageIndexStore instance
        top_k: Number of chunks to retrieve
        
    Returns:
        PageIndexRetriever instance
    """
    return PageIndexRetriever(store=store, top_k=top_k)
