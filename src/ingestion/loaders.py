from pathlib import Path
from typing import Optional
import PyPDF2
import pdfplumber
from ..core.models import Document
from ..core.utils import get_file_size, compute_text_hash, clean_text
from ..core.logging_config import get_logger
from ..core.exceptions import DocumentIngestionError

logger = get_logger(__name__)


class DocumentLoader:
    """Base class for document loaders."""
    
    @staticmethod
    def load_txt(file_path: str) -> Document:
        """Load a text file.
        
        Args:
            file_path: Path to the text file
            
        Returns:
            Document object
        """
        try:
            path = Path(file_path)
            
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Clean content
            content = clean_text(content)
            
            # Generate metadata
            content_hash = compute_text_hash(content)
            doc_id = Document.generate_doc_id(str(path), content_hash)
            
            doc = Document(
                doc_id=doc_id,
                content=content,
                source=str(path.absolute()),
                filename=path.name,
                file_type='txt',
                file_size=get_file_size(file_path),
                content_hash=content_hash,
                metadata={
                    'loader': 'txt'
                }
            )
            
            logger.info(f"Loaded TXT file: {path.name}")
            return doc
            
        except Exception as e:
            raise DocumentIngestionError(f"Failed to load TXT file {file_path}: {str(e)}")
    
    @staticmethod
    def load_pdf(file_path: str, use_pdfplumber: bool = True) -> Document:
        """Load a PDF file.
        
        Args:
            file_path: Path to the PDF file
            use_pdfplumber: Use pdfplumber (better text extraction) vs PyPDF2
            
        Returns:
            Document object
        """
        try:
            path = Path(file_path)
            
            if use_pdfplumber:
                content = DocumentLoader._extract_pdf_pdfplumber(path)
            else:
                content = DocumentLoader._extract_pdf_pypdf2(path)
            
            # Clean content
            content = clean_text(content)
            
            # Generate metadata
            content_hash = compute_text_hash(content)
            doc_id = Document.generate_doc_id(str(path), content_hash)
            
            doc = Document(
                doc_id=doc_id,
                content=content,
                source=str(path.absolute()),
                filename=path.name,
                file_type='pdf',
                file_size=get_file_size(file_path),
                content_hash=content_hash,
                metadata={
                    'loader': 'pdfplumber' if use_pdfplumber else 'pypdf2'
                }
            )
            
            logger.info(f"Loaded PDF file: {path.name}")
            return doc
            
        except Exception as e:
            raise DocumentIngestionError(f"Failed to load PDF file {file_path}: {str(e)}")
    
    @staticmethod
    def _extract_pdf_pypdf2(path: Path) -> str:
        """Extract text from PDF using PyPDF2."""
        text_parts = []
        
        with open(path, 'rb') as f:
            pdf_reader = PyPDF2.PdfReader(f)
            for page in pdf_reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
        
        return '\n\n'.join(text_parts)
    
    @staticmethod
    def _extract_pdf_pdfplumber(path: Path) -> str:
        """Extract text from PDF using pdfplumber (better quality)."""
        text_parts = []
        
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
        
        return '\n\n'.join(text_parts)
    
    @staticmethod
    def load_markdown(file_path: str) -> Document:
        """Load a Markdown file.
        
        Args:
            file_path: Path to the Markdown file
            
        Returns:
            Document object
        """
        try:
            path = Path(file_path)
            
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Clean content (preserve markdown formatting)
            content = clean_text(content)
            
            # Generate metadata
            content_hash = compute_text_hash(content)
            doc_id = Document.generate_doc_id(str(path), content_hash)
            
            doc = Document(
                doc_id=doc_id,
                content=content,
                source=str(path.absolute()),
                filename=path.name,
                file_type='md',
                file_size=get_file_size(file_path),
                content_hash=content_hash,
                metadata={
                    'loader': 'markdown'
                }
            )
            
            logger.info(f"Loaded Markdown file: {path.name}")
            return doc
            
        except Exception as e:
            raise DocumentIngestionError(f"Failed to load Markdown file {file_path}: {str(e)}")
    
    @staticmethod
    def load_file(file_path: str) -> Document:
        """Load a file based on its extension.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Document object
        """
        path = Path(file_path)
        extension = path.suffix.lower()
        
        if extension == '.txt':
            return DocumentLoader.load_txt(file_path)
        elif extension == '.pdf':
            return DocumentLoader.load_pdf(file_path)
        elif extension in ['.md', '.markdown']:
            return DocumentLoader.load_markdown(file_path)
        else:
            raise DocumentIngestionError(f"Unsupported file type: {extension}")
