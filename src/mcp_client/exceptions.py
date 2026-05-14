"""Custom exceptions for the MCP client module."""


class MCPConnectionError(Exception):
    """Raised when transport connection or protocol handshake fails."""


class MCPToolError(Exception):
    """Raised when the remote MCP server returns isError=true for a tool call."""


class MCPProtocolError(Exception):
    """Raised when the MCP server returns a structurally invalid response."""
