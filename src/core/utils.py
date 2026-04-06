import hashlib
import re
from pathlib import Path
from typing import Optional, List
import unicodedata


def compute_file_hash(file_path: str) -> str:
    """Compute SHA-256 hash of a file.
    
    Args:
        file_path: Path to the file
        
    Returns:
        Hexadecimal hash string
    """
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def compute_text_hash(text: str) -> str:
    """Compute SHA-256 hash of text content.
    
    Args:
        text: Text content
        
    Returns:
        Hexadecimal hash string
    """
    return hashlib.sha256(text.encode()).hexdigest()


def normalize_text(text: str) -> str:
    """Normalize text by removing extra whitespace and special characters.
    
    Args:
        text: Input text
        
    Returns:
        Normalized text
    """
    # Normalize unicode characters
    text = unicodedata.normalize('NFKD', text)
    
    # Replace multiple whitespace with single space
    text = re.sub(r'\s+', ' ', text)
    
    # Remove leading/trailing whitespace
    text = text.strip()
    
    return text


def clean_text(text: str) -> str:
    """Clean text by removing formatting artifacts and normalizing.
    
    Args:
        text: Input text
        
    Returns:
        Cleaned text
    """
    # Remove zero-width characters
    text = re.sub(r'[\u200b\u200c\u200d\ufeff]', '', text)
    
    # Remove excessive newlines (more than 2)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Normalize text
    text = normalize_text(text)
    
    return text


def get_file_extension(file_path: str) -> str:
    """Get file extension from path.
    
    Args:
        file_path: Path to file
        
    Returns:
        File extension without dot (e.g., 'txt', 'pdf')
    """
    return Path(file_path).suffix.lstrip('.').lower()


def get_file_size(file_path: str) -> int:
    """Get file size in bytes.
    
    Args:
        file_path: Path to file
        
    Returns:
        File size in bytes
    """
    return Path(file_path).stat().st_size


def ensure_directory(dir_path: str) -> Path:
    """Ensure directory exists, create if it doesn't.
    
    Args:
        dir_path: Directory path
        
    Returns:
        Path object
    """
    path = Path(dir_path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """Truncate text to maximum length.
    
    Args:
        text: Input text
        max_length: Maximum length
        suffix: Suffix to add when truncated
        
    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def split_into_sentences(text: str) -> List[str]:
    """Split text into sentences using simple heuristics.
    
    Args:
        text: Input text
        
    Returns:
        List of sentences
    """
    # Simple sentence splitting (can be improved with nltk if needed)
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in sentences if s.strip()]


def extract_keywords(text: str, max_keywords: int = 10) -> List[str]:
    """Extract simple keywords from text (basic implementation).
    
    Args:
        text: Input text
        max_keywords: Maximum number of keywords
        
    Returns:
        List of keywords
    """
    # Convert to lowercase and split
    words = text.lower().split()
    
    # Remove common stop words (basic list)
    stop_words = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
        'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'be',
        'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
        'would', 'could', 'should', 'may', 'might', 'can', 'this', 'that',
        'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they'
    }
    
    # Filter words
    keywords = [w for w in words if w not in stop_words and len(w) > 2]
    
    # Count frequency
    word_freq = {}
    for word in keywords:
        word_freq[word] = word_freq.get(word, 0) + 1
    
    # Sort by frequency and return top keywords
    sorted_keywords = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
    return [word for word, _ in sorted_keywords[:max_keywords]]
