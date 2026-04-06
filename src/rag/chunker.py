from langchain.text_splitter import RecursiveCharacterTextSplitter
from typing import List
from ..core.models import Document, Chunk
from ..config.models import RAGConfig
from ..core.logging_config import get_logger
import hashlib

logger = get_logger(__name__)


class DocumentChunker:
    """Chunk documents into smaller pieces for RAG."""
    
    def __init__(self, config: RAGConfig):
        self.config = config
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
    
    def chunk_document(self, document: Document) -> Document:
        """Chunk a document into smaller pieces.
        
        Args:
            document: Document to chunk
            
        Returns:
            Document with chunks populated
        """
        # Split text into chunks
        text_chunks = self.text_splitter.split_text(document.content)
        
        # Create Chunk objects
        chunks = []
        current_pos = 0
        
        for i, chunk_text in enumerate(text_chunks):
            # Find the position of this chunk in the original text
            start_index = document.content.find(chunk_text, current_pos)
            end_index = start_index + len(chunk_text)
            
            # Generate chunk ID
            chunk_id = self._generate_chunk_id(document.doc_id, i)
            
            # Create Chunk object
            chunk = Chunk(
                chunk_id=chunk_id,
                doc_id=document.doc_id,
                content=chunk_text,
                start_index=start_index,
                end_index=end_index,
                metadata={
                    "chunk_index": i,
                    "source": document.source,
                    "filename": document.filename
                }
            )
            chunks.append(chunk)
            
            # Update position for next search
            current_pos = end_index
        
        # Add chunks to document
        document.chunks = chunks
        
        logger.debug(f"Chunked document {document.doc_id} into {len(chunks)} chunks")
        return document
    
    def chunk_documents(self, documents: List[Document]) -> List[Document]:
        """Chunk multiple documents.
        
        Args:
            documents: List of documents to chunk
            
        Returns:
            List of documents with chunks populated
        """
        chunked_docs = []
        for doc in documents:
            chunked_doc = self.chunk_document(doc)
            chunked_docs.append(chunked_doc)
        
        total_chunks = sum(len(doc.chunks) for doc in chunked_docs)
        logger.info(f"Chunked {len(documents)} documents into {total_chunks} total chunks")
        
        return chunked_docs
    
    def _generate_chunk_id(self, doc_id: str, chunk_index: int) -> str:
        """Generate a unique chunk ID."""
        combined = f"{doc_id}:chunk:{chunk_index}"
        return hashlib.md5(combined.encode()).hexdigest()
