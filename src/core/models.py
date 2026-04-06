from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field
import hashlib


class Chunk(BaseModel):
    """Represents a chunk of text from a document."""
    
    chunk_id: str = Field(description="Unique identifier for the chunk")
    doc_id: str = Field(description="Parent document identifier")
    content: str = Field(description="Text content of the chunk")
    start_index: int = Field(description="Start position in original document")
    end_index: int = Field(description="End position in original document")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    class Config:
        frozen = False


class Document(BaseModel):
    """Represents a document in the RAG system."""
    
    doc_id: str = Field(description="Unique identifier for the document")
    content: str = Field(description="Full text content of the document")
    source: str = Field(description="Source file path or URL")
    filename: str = Field(description="Original filename")
    file_type: str = Field(description="File type (txt, pdf, md, etc.)")
    file_size: int = Field(default=0, description="File size in bytes")
    content_hash: str = Field(description="Hash of content for duplicate detection")
    chunks: List[Chunk] = Field(default_factory=list, description="Document chunks")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    created_at: datetime = Field(default_factory=datetime.now, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.now, description="Last update timestamp")
    
    class Config:
        frozen = False
    
    @staticmethod
    def generate_content_hash(content: str) -> str:
        """Generate SHA-256 hash of content for duplicate detection."""
        return hashlib.sha256(content.encode()).hexdigest()
    
    @staticmethod
    def generate_doc_id(source: str, content_hash: str) -> str:
        """Generate unique document ID from source and content hash."""
        combined = f"{source}:{content_hash}"
        return hashlib.md5(combined.encode()).hexdigest()


class Message(BaseModel):
    """Represents a chat message."""
    
    role: str = Field(description="Message role: 'user' or 'assistant'")
    content: str = Field(description="Message content")
    timestamp: datetime = Field(default_factory=datetime.now, description="Message timestamp")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    class Config:
        frozen = False


class Conversation(BaseModel):
    """Represents a conversation session."""
    
    conversation_id: str = Field(description="Unique conversation identifier")
    messages: List[Message] = Field(default_factory=list, description="List of messages")
    created_at: datetime = Field(default_factory=datetime.now, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.now, description="Last update timestamp")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    class Config:
        frozen = False
    
    def add_message(self, role: str, content: str, metadata: Optional[Dict[str, Any]] = None):
        """Add a message to the conversation."""
        message = Message(role=role, content=content, metadata=metadata or {})
        self.messages.append(message)
        self.updated_at = datetime.now()
    
    def get_recent_messages(self, limit: int = 10) -> List[Message]:
        """Get the most recent messages."""
        return self.messages[-limit:] if len(self.messages) > limit else self.messages
