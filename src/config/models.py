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
    semantic_search_enabled: bool = Field(default=False)
    vector_store_config: Optional[dict] = Field(default=None)
    
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


class MemoryConfig(BaseModel):
    enabled: bool = Field(default=True)
    store_path: str = Field(default="data/memory/memories.db")
    max_context_items: int = Field(default=8)
    context_window: int = Field(default=2000)


class TasksConfig(BaseModel):
    enabled: bool = Field(default=False)
    require_confirmation: bool = Field(default=True)
    task_clients: List[dict] = Field(default_factory=list)


class LearningConfig(BaseModel):
    enabled: bool = Field(default=True)
    adaptation_rate: float = Field(default=0.1)
    positive_increment: float = Field(default=0.1)
    negative_decrement: float = Field(default=0.08)


class ProactiveConfig(BaseModel):
    enabled: bool = Field(default=False)
    briefing_hour: int = Field(default=9)
    cycle_interval_minutes: int = Field(default=30)
    quiet_hours_start: int = Field(default=22)
    quiet_hours_end: int = Field(default=8)


class NewsConfig(BaseModel):
    enabled: bool = Field(default=False)
    db_path: str = Field(default="data/news/news.db")
    region: str = Field(default="wt-wt")  # wt-wt = worldwide/any language
    default_fetch_interval_minutes: int = Field(default=60, ge=5, le=1440)
    default_max_articles_per_fetch: int = Field(default=10, ge=1, le=100)
    summarise_on_fetch: bool = Field(default=True)
    ingest_into_rag: bool = Field(default=False)
    max_content_chars: int = Field(default=8000, ge=100)
    summary_max_sentences: int = Field(default=5, ge=1)
    retention_days: int = Field(default=3, ge=1)
    cleanup_interval_hours: int = Field(default=6, ge=1)


class MCPClientConfig(BaseModel):
    store_path: str = Field(default="data/mcp_client/servers.db")


class VoiceWakeWordConfig(BaseModel):
    phrase: str = Field(default="hey_jarvis")
    model_path: Optional[str] = Field(default=None)
    threshold: float = Field(default=0.5, ge=0.0, le=1.0)


class VoiceSTTConfig(BaseModel):
    engine: str = Field(default="faster-whisper")
    model_size: str = Field(default="base")
    language: str = Field(default="en")
    device: str = Field(default="cpu")
    compute_type: str = Field(default="int8")


class VoiceTTSConfig(BaseModel):
    engine: str = Field(default="edge-tts")
    voice: str = Field(default="en-US-JennyNeural")
    rate: str = Field(default="+0%")
    fallback_engine: str = Field(default="pyttsx3")


class VoiceConfig(BaseModel):
    enabled: bool = Field(default=False)
    wake_word: VoiceWakeWordConfig = Field(default_factory=VoiceWakeWordConfig)
    stt: VoiceSTTConfig = Field(default_factory=VoiceSTTConfig)
    tts: VoiceTTSConfig = Field(default_factory=VoiceTTSConfig)
    vad_silence_ms: int = Field(default=800, ge=200, le=3000)
    barge_in_threshold: float = Field(default=0.015, ge=0.0, le=1.0)
    llm_model: str = Field(default="llama3.2")
    use_agent: bool = Field(default=True)
    conversation_id_prefix: str = Field(default="voice")
    # The voice assistant acts as the personal assistant of whichever user is
    # currently logged into the web UI (see src/auth/session_bridge.py) — it
    # does not have its own separate account. If nobody is logged in, it
    # refuses to act and asks the user to log in.
    command_history_days: int = Field(default=3, ge=1, le=90)
    command_history_db: str = Field(default="data/voice/commands.db")


class AuthConfig(BaseModel):
    enabled: bool = Field(default=True)
    db_path: str = Field(default="data/auth/users.db")
    access_token_expire_minutes: int = Field(default=30, ge=1)
    refresh_token_expire_days: int = Field(default=7, ge=1)


class ActivityConfig(BaseModel):
    enabled: bool = Field(default=True)
    store_path: str = Field(default="data/activity/activity.db")


class EmailConfig(BaseModel):
    """SMTP email delivery (password reset, etc.). Credentials come from env vars —
    never hardcode them in config.yaml. When smtp_host is unset, emails are logged
    instead of sent (dev-friendly fallback)."""
    enabled: bool = Field(default=False)
    smtp_host: Optional[str] = Field(default=None)
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: Optional[str] = Field(default=None)  # env: RAGENIE_SMTP_USERNAME
    smtp_password_env: str = Field(default="RAGENIE_SMTP_PASSWORD")
    use_tls: bool = Field(default=True)
    from_address: str = Field(default="no-reply@ragenie.local")
    from_name: str = Field(default="RAGenie")
    frontend_base_url: str = Field(default="http://localhost:3000")
    reset_token_expire_minutes: int = Field(default=30, ge=1)


class RateLimitConfig(BaseModel):
    enabled: bool = Field(default=True)
    default_rpm: int = Field(default=60, ge=1)
    upload_rph: int = Field(default=10, ge=1)
    ws_rpm: int = Field(default=30, ge=1)


class SecurityConfig(BaseModel):
    rate_limiting: RateLimitConfig = Field(default_factory=RateLimitConfig)
    security_headers: bool = Field(default=True)
    log_redaction: bool = Field(default=True)
    max_request_size_mb: int = Field(default=30, ge=1)
    ws_max_message_length: int = Field(default=10000, ge=1)
    audit_log_path: str = Field(default="logs/audit.log")


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
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    tasks: TasksConfig = Field(default_factory=TasksConfig)
    learning: LearningConfig = Field(default_factory=LearningConfig)
    proactive: ProactiveConfig = Field(default_factory=ProactiveConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)
    news: NewsConfig = Field(default_factory=NewsConfig)
    mcp_client: MCPClientConfig = Field(default_factory=MCPClientConfig)
    voice: VoiceConfig = Field(default_factory=VoiceConfig)
    activity: ActivityConfig = Field(default_factory=ActivityConfig)
    email: EmailConfig = Field(default_factory=EmailConfig)

    @validator("mcp_server")
    def validate_mcp_server_mode(cls, v, values):
        mode = values.get("mode")
        if mode in ["hybrid", "mcp_server"]:
            v.enabled = True
        return v
