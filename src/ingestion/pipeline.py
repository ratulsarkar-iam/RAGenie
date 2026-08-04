from pathlib import Path
from typing import List, Dict, Any
from .loaders import DocumentLoader
from ..rag.chunker import DocumentChunker
from ..rag.page_index_store import PageIndexStore
from ..config.models import RAGConfig
from ..core.models import Document
from ..core.logging_config import get_logger
from ..core.exceptions import DocumentIngestionError

logger = get_logger(__name__)


class IngestionPipeline:
    """Pipeline for ingesting documents into the RAG system."""
    
    def __init__(self, store: PageIndexStore, chunker: DocumentChunker):
        self.store = store
        self.chunker = chunker
        self.loader = DocumentLoader()
    
    def ingest_file(self, file_path: str, user_id: str = "") -> Document:
        """Ingest a single file.
        
        Args:
            file_path: Path to the file
            user_id: Owning user's id — scopes visibility/duplicate checks to that user,
                same as news keywords are scoped per user.
            
        Returns:
            Ingested Document
        """
        logger.info(f"Ingesting file: {file_path} (user={user_id or 'unowned'})")
        
        # Load document
        doc = self.loader.load_file(file_path)
        doc.user_id = user_id
        
        # Check for duplicates (scoped to this user only)
        if self._is_duplicate(doc):
            logger.warning(f"Duplicate document detected: {doc.filename}")
            raise DocumentIngestionError(f"Document already exists: {doc.filename}")
        
        # Chunk document
        doc = self.chunker.chunk_document(doc)
        
        # Add to store
        self.store.add_documents([doc])
        
        logger.info(f"Successfully ingested: {doc.filename} ({len(doc.chunks)} chunks)")
        return doc
    
    def ingest_directory(self, directory_path: str, recursive: bool = True) -> List[Document]:
        """Ingest all supported files from a directory.
        
        Args:
            directory_path: Path to the directory
            recursive: Whether to search recursively
            
        Returns:
            List of ingested Documents
        """
        path = Path(directory_path)
        
        if not path.is_dir():
            raise DocumentIngestionError(f"Not a directory: {directory_path}")
        
        # Find all supported files
        supported_extensions = {
            '.txt', '.pdf', '.md', '.markdown',
            '.docx', '.doc',
            '.xlsx', '.xls', '.csv',
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.svg',
            '.mp3', '.wav', '.ogg', '.flac', '.m4a', '.aac', '.wma',
        }
        
        if recursive:
            files = [f for f in path.rglob('*') if f.suffix.lower() in supported_extensions]
        else:
            files = [f for f in path.glob('*') if f.suffix.lower() in supported_extensions]
        
        logger.info(f"Found {len(files)} files to ingest from {directory_path}")
        
        # Ingest files
        ingested_docs = []
        failed_files = []
        
        for file_path in files:
            try:
                doc = self.ingest_file(str(file_path))
                ingested_docs.append(doc)
            except Exception as e:
                logger.error(f"Failed to ingest {file_path}: {str(e)}")
                failed_files.append((str(file_path), str(e)))
        
        # Save index
        self.store.save()
        
        # Report results
        logger.info(f"Ingestion complete: {len(ingested_docs)} succeeded, {len(failed_files)} failed")
        
        if failed_files:
            logger.warning("Failed files:")
            for file_path, error in failed_files:
                logger.warning(f"  - {file_path}: {error}")
        
        return ingested_docs
    
    def ingest_files(self, file_paths: List[str]) -> List[Document]:
        """Ingest multiple files.
        
        Args:
            file_paths: List of file paths
            
        Returns:
            List of ingested Documents
        """
        ingested_docs = []
        failed_files = []
        
        for file_path in file_paths:
            try:
                doc = self.ingest_file(file_path)
                ingested_docs.append(doc)
            except Exception as e:
                logger.error(f"Failed to ingest {file_path}: {str(e)}")
                failed_files.append((file_path, str(e)))
        
        # Save index
        self.store.save()
        
        logger.info(f"Batch ingestion complete: {len(ingested_docs)} succeeded, {len(failed_files)} failed")
        return ingested_docs
    
    def _is_duplicate(self, doc: Document) -> bool:
        """Check if document is a duplicate based on content hash, scoped to
        the same user (two different users may independently upload the same file).
        
        Args:
            doc: Document to check
            
        Returns:
            True if duplicate exists
        """
        for existing_doc in self.store.list_documents(user_id=doc.user_id or None):
            if existing_doc.content_hash == doc.content_hash:
                return True
        return False
    
    def get_ingestion_stats(self) -> Dict[str, Any]:
        """Get statistics about ingested documents.
        
        Returns:
            Dictionary with statistics
        """
        docs = self.store.list_documents()
        
        stats = {
            "total_documents": len(docs),
            "total_chunks": sum(len(doc.chunks) for doc in docs),
            "file_types": {},
            "total_size_bytes": sum(doc.file_size for doc in docs)
        }
        
        # Count by file type
        for doc in docs:
            file_type = doc.file_type
            stats["file_types"][file_type] = stats["file_types"].get(file_type, 0) + 1
        
        return stats
