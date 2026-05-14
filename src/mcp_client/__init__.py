"""MCP Client package — connects RAGenie to external MCP servers."""
from .models import (
    ServerConfig, ServerConfigCreate, ServerConfigPatch,
    ServerStatus, ToolDefinition, ServerWithStatus, ConnectionStatus,
    ServerCreateRequest, ImportRequest, ImportResult, TestResult,
    ToolCallTrace, MCPChatRequest, MCPChatResponse, MCPChatMessage,
)
from .exceptions import MCPConnectionError, MCPToolError, MCPProtocolError
from .server_store import ServerConfigStore
from .client import MCPClientConnection
from .manager import MCPClientManager

__all__ = [
    "ServerConfig", "ServerConfigCreate", "ServerConfigPatch",
    "ServerStatus", "ToolDefinition", "ServerWithStatus", "ConnectionStatus",
    "ServerCreateRequest", "ImportRequest", "ImportResult", "TestResult",
    "ToolCallTrace", "MCPChatRequest", "MCPChatResponse", "MCPChatMessage",
    "MCPConnectionError", "MCPToolError", "MCPProtocolError",
    "ServerConfigStore", "MCPClientConnection", "MCPClientManager",
]
