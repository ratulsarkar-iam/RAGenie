from typing import List
from ..core.models import Chunk
from ..core.logging_config import get_logger

logger = get_logger(__name__)


class ContextBuilder:
    """Build context from retrieved chunks for prompt augmentation."""
    
    def __init__(self, max_context_length: int = 2000):
        self.max_context_length = max_context_length
    
    def build_context(self, chunks: List[Chunk]) -> str:
        """Build context string from chunks.
        
        Args:
            chunks: List of retrieved chunks
            
        Returns:
            Formatted context string
        """
        if not chunks:
            return ""
        
        context_parts = []
        current_length = 0
        
        for i, chunk in enumerate(chunks):
            # Format chunk with metadata
            chunk_text = f"[Source: {chunk.metadata.get('filename', 'Unknown')}]\n{chunk.content}\n"
            chunk_length = len(chunk_text)
            
            # Check if adding this chunk would exceed max length
            if current_length + chunk_length > self.max_context_length:
                logger.debug(f"Reached max context length, using {i} chunks")
                break
            
            context_parts.append(chunk_text)
            current_length += chunk_length
        
        context = "\n---\n".join(context_parts)
        logger.debug(f"Built context from {len(context_parts)} chunks ({current_length} chars)")
        
        return context
    
    def augment_prompt(self, query: str, chunks: List[Chunk]) -> str:
        """Augment a query with retrieved context.
        
        Args:
            query: User query
            chunks: Retrieved chunks
            
        Returns:
            Augmented prompt with context
        """
        context = self.build_context(chunks)
        
        if not context:
            return query
        
        augmented = f"""Use the following context to answer the question. If the context doesn't contain relevant information, say so.

Context:
{context}

Question: {query}

Answer:"""
        
        return augmented
