"""Pydantic models for the activity log."""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel


class ActivityEventType(str, Enum):
    LOGIN = "login"
    LOGOUT = "logout"
    CHAT_MESSAGE = "chat_message"
    DOCUMENT_UPLOADED = "document_uploaded"
    DOCUMENT_DELETED = "document_deleted"
    KEYWORD_CREATED = "keyword_created"
    KEYWORD_UPDATED = "keyword_updated"
    KEYWORD_DELETED = "keyword_deleted"
    NEWS_SEARCH = "news_search"
    NEWS_FETCH_NOW = "news_fetch_now"
    MCP_SERVER_CREATED = "mcp_server_created"
    MCP_SERVER_UPDATED = "mcp_server_updated"
    MCP_SERVER_DELETED = "mcp_server_deleted"
    MCP_SERVER_CONNECTED = "mcp_server_connected"
    MCP_SERVER_DISCONNECTED = "mcp_server_disconnected"
    MCP_TOOL_CALL = "mcp_tool_call"
    MEMORY_SEARCH = "memory_search"


class ActivityEvent(BaseModel):
    id: str
    user_id: str
    event_type: str
    description: str
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime


class ActivityEventCreate(BaseModel):
    user_id: str
    event_type: str
    description: str
    metadata: Optional[Dict[str, Any]] = None
