from typing import List, Optional, Literal, Dict
from pydantic import BaseModel, Field, validator


class ModelConfig(BaseModel):
    """Configuration for a single model."""
    provider: Literal["ollama", "huggingface"] = Field(default="ollama")
    model_name: str = Field(default="llama3.2")
    base_url: str = Field(default="http://localhost:11434")
    max_tokens: int = Field(default=512, ge=1, le=4096)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    top_p: float = Field(default=0.9, ge=0.0, le=1.0)
    top_k: int = Field(default=50, ge=1)
    quantization: Optional[Literal["4bit", "8bit", "none"]] = Field(default="none")
    device: Optional[Literal["mps", "cuda", "cpu"]] = Field(default="mps")
    role: Optional[Literal["reasoning", "main", "fallback"]] = Field(default=None)


class LLMConfig(BaseModel):
    """LLM configuration supporting both single and multi-model setups."""
    provider: Literal["ollama", "huggingface"] = Field(default="ollama")
    model_name: str = Field(default="llama3.2")
    base_url: str = Field(default="http://localhost:11434")
    max_tokens: int = Field(default=512, ge=1, le=4096)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    top_p: float = Field(default=0.9, ge=0.0, le=1.0)
    top_k: int = Field(default=50, ge=1)
    quantization: Optional[Literal["4bit", "8bit", "none"]] = Field(default="none")
    device: Optional[Literal["mps", "cuda", "cpu"]] = Field(default="mps")
    multi_model: Optional[Dict[str, ModelConfig]] = Field(default=None)


class RAGConfig(BaseModel):
    storage_type: Literal["page_index", "vector_db"] = Field(default="page_index")
    chunk_size: int = Field(default=1000, ge=100, le=4000)
    chunk_overlap: int = Field(default=200, ge=0, le=1000)
    top_k: int = Field(default=3, ge=1, le=10)
    index_path: str = Field(default="data/index/page_index.json")
    auto_web_search: bool = Field(default=True)
    web_search_threshold: float = Field(default=0.3)  # Relevance threshold
    
    @validator("chunk_overlap")
    def validate_overlap(cls, v, values):
        if "chunk_size" in values and v >= values["chunk_size"]:
            raise ValueError("chunk_overlap must be less than chunk_size")
        return v


class SearchConfig(BaseModel):
    provider: Literal["duckduckgo"] = Field(default="duckduckgo")
    max_results: int = Field(default=5, ge=1, le=20)
    cache_ttl_seconds: int = Field(default=3600, ge=0)


class ServerConfig(BaseModel):
    host: str = Field(default="localhost")
    port: int = Field(default=8000, ge=1024, le=65535)
    cors_origins: List[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://localhost:5173"]
    )


class MCPServerConfig(BaseModel):
    enabled: bool = Field(default=True)
    transport: Literal["stdio", "sse"] = Field(default="sse")
    name: str = Field(default="rag-search-server")
    port: int = Field(default=8001, ge=1024, le=65535)


class MCPClientServerConfig(BaseModel):
    name: str
    enabled: bool = Field(default=True)
    transport: Literal["stdio", "sse"]
    command: Optional[str] = None
    args: Optional[List[str]] = None
    env: Optional[dict] = None
    url: Optional[str] = None

    @validator("command")
    def validate_stdio_command(cls, v, values):
        if values.get("transport") == "stdio" and not v:
            raise ValueError("command is required for stdio transport")
        return v

    @validator("url")
    def validate_sse_url(cls, v, values):
        if values.get("transport") == "sse" and not v:
            raise ValueError("url is required for sse transport")
        return v


class ConversationConfig(BaseModel):
    max_history: int = Field(default=10, ge=1, le=100)
    db_path: str = Field(default="data/conversations.db")


class LoggingConfig(BaseModel):
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO"
    )
    format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    file: str = Field(default="logs/chatbot.log")


class Config(BaseModel):
    mode: Literal["hybrid", "chatbot", "mcp_server"] = Field(default="hybrid")
    llm: LLMConfig = Field(default_factory=LLMConfig)
    rag: RAGConfig = Field(default_factory=RAGConfig)
    search: SearchConfig = Field(default_factory=SearchConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    mcp_server: MCPServerConfig = Field(default_factory=MCPServerConfig)
    mcp_clients: List[MCPClientServerConfig] = Field(default_factory=list)
    conversation: ConversationConfig = Field(default_factory=ConversationConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    @validator("mcp_server")
    def validate_mcp_server_mode(cls, v, values):
        mode = values.get("mode")
        if mode in ["hybrid", "mcp_server"]:
            v.enabled = True
        return v
