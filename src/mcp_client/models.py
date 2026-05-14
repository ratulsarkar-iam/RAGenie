"""Pydantic models for the MCP client module."""
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class ConnectionStatus(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


class ServerConfig(BaseModel):
    id: str
    name: str
    transport: Literal["stdio", "sse", "http"]
    enabled: bool = True

    command: Optional[str] = None
    args: Optional[List[str]] = None
    env: Optional[Dict[str, str]] = None

    url: Optional[str] = None
    headers: Optional[Dict[str, str]] = None

    created_at: str
    updated_at: str


class ServerConfigCreate(BaseModel):
    name: str
    transport: Literal["stdio", "sse", "http"]
    enabled: bool = True

    command: Optional[str] = None
    args: Optional[List[str]] = None
    env: Optional[Dict[str, str]] = None

    url: Optional[str] = None
    headers: Optional[Dict[str, str]] = None


class ServerConfigPatch(BaseModel):
    name: Optional[str] = None
    transport: Optional[Literal["stdio", "sse", "http"]] = None
    enabled: Optional[bool] = None
    command: Optional[str] = None
    args: Optional[List[str]] = None
    env: Optional[Dict[str, str]] = None
    url: Optional[str] = None
    headers: Optional[Dict[str, str]] = None


class ServerStatus(BaseModel):
    server_id: str
    status: ConnectionStatus
    error_message: Optional[str] = None
    tool_count: int = 0
    last_connected_at: Optional[str] = None
    session_meta: Dict[str, Any] = Field(default_factory=dict)


class ToolDefinition(BaseModel):
    server_id: str
    server_name: str
    tool_id: str
    name: str
    description: str
    input_schema: dict


class ServerWithStatus(BaseModel):
    config: ServerConfig
    status: ServerStatus
    tools: List[ToolDefinition] = []


class ServerCreateRequest(ServerConfigCreate):
    """API-layer extension of ServerConfigCreate — adds connect_now (not persisted)."""
    connect_now: bool = True


class ImportRequest(BaseModel):
    mcpServers: Dict[str, dict]
    connect_now: bool = False


class ImportResult(BaseModel):
    created: int
    updated: int
    skipped: int


class TestResult(BaseModel):
    success: bool
    tool_count: int = 0
    tools: List[ToolDefinition] = []
    latency_ms: Optional[int] = None
    error: Optional[str] = None


# ── MCP agent-chat models ─────────────────────────────────────────────────────

class ToolCallTrace(BaseModel):
    tool_name: str
    args: Dict[str, Any] = {}
    result: str


class MCPChatRequest(BaseModel):
    message: str
    conversation_id: str = "mcp-chat-default"
    tool_filter: Optional[List[str]] = None  # None = all connected tools


class MCPChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str
    tool_calls: List[ToolCallTrace] = []


class MCPChatResponse(BaseModel):
    response: str
    conversation_id: str
    tool_calls: List[ToolCallTrace] = []
    history: List[MCPChatMessage] = []
