"""Custom exceptions for the RAG chatbot application."""


class RagChatbotException(Exception):
    """Base exception for all RAG chatbot errors."""
    pass


class ConfigurationError(RagChatbotException):
    """Raised when there's a configuration error."""
    pass


class ModelLoadError(RagChatbotException):
    """Raised when LLM model fails to load."""
    pass


class DocumentStoreError(RagChatbotException):
    """Raised when document store operations fail."""
    pass


class DocumentNotFoundError(DocumentStoreError):
    """Raised when a requested document is not found."""
    pass


class DocumentIngestionError(RagChatbotException):
    """Raised when document ingestion fails."""
    pass


class SearchError(RagChatbotException):
    """Raised when search operations fail."""
    pass


class MCPConnectionError(RagChatbotException):
    """Raised when MCP server connection fails."""
    pass


class MCPToolExecutionError(RagChatbotException):
    """Raised when MCP tool execution fails."""
    pass


class ConversationError(RagChatbotException):
    """Raised when conversation operations fail."""
    pass


class GenerationError(RagChatbotException):
    """Raised when text generation fails."""
    pass


class ValidationError(RagChatbotException):
    """Raised when input validation fails."""
    pass
