"""MCPClientConnection — wraps the MCP Python SDK for a single server connection."""
import asyncio
import time
from datetime import datetime, timezone
from typing import List, Optional

from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamablehttp_client

from .exceptions import MCPConnectionError, MCPToolError
from .models import ConnectionStatus, ServerConfig, ServerStatus, ToolDefinition
from ..core.logging_config import get_logger

logger = get_logger(__name__)

_RECONNECT_DELAYS = [10, 30, 60]
_CONNECT_TIMEOUT = 30.0
_TOOL_CALL_TIMEOUT = 30.0


class MCPClientConnection:
    """Manages a persistent connection to a single MCP server."""

    def __init__(self, config: ServerConfig):
        self._config = config
        self._session: Optional[ClientSession] = None
        self._task: Optional[asyncio.Task] = None
        self._stop_event: asyncio.Event = asyncio.Event()
        self._ready_event: asyncio.Event = asyncio.Event()
        self._status = ConnectionStatus.DISCONNECTED
        self._error_message: Optional[str] = None
        self._tools: List[ToolDefinition] = []
        self._session_id: Optional[str] = None
        self._last_connected_at: Optional[str] = None
        self._reconnect_enabled = True

    # ── Public API ──────────────────────────────────────────────────────────

    async def connect(self) -> None:
        """Start the connection. Blocks until the session is ready or raises."""
        self._stop_event.clear()
        self._ready_event.clear()
        self._status = ConnectionStatus.CONNECTING
        self._error_message = None

        self._task = asyncio.create_task(
            self._run_with_reconnect(), name=f"mcp-{self._config.name}"
        )

        try:
            await asyncio.wait_for(self._ready_event.wait(), timeout=_CONNECT_TIMEOUT)
        except asyncio.TimeoutError:
            self._task.cancel()
            raise MCPConnectionError(
                f"Timed out connecting to '{self._config.name}' after {_CONNECT_TIMEOUT}s"
            )

        if self._status == ConnectionStatus.ERROR:
            raise MCPConnectionError(
                self._error_message or f"Connection failed: {self._config.name}"
            )

    async def disconnect(self) -> None:
        """Gracefully stop the connection."""
        self._reconnect_enabled = False
        self._stop_event.set()
        if self._task and not self._task.done():
            try:
                await asyncio.wait_for(self._task, timeout=10.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self._task.cancel()
        self._session = None
        self._status = ConnectionStatus.DISCONNECTED
        self._tools = []
        logger.info(f"Disconnected from MCP server '{self._config.name}'")

    async def call_tool(self, name: str, args: dict, timeout: float = _TOOL_CALL_TIMEOUT) -> str:
        """Call a tool by its bare name (not the namespaced tool_id)."""
        if self._session is None or self._status != ConnectionStatus.CONNECTED:
            raise MCPConnectionError(
                f"Not connected to '{self._config.name}' (status={self._status})"
            )
        try:
            result = await asyncio.wait_for(
                self._session.call_tool(name, args or {}),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            raise asyncio.TimeoutError(
                f"Tool '{name}' on '{self._config.name}' timed out after {timeout}s"
            )

        if result.isError:
            texts = [c.text for c in result.content if hasattr(c, "text")]
            raise MCPToolError("; ".join(texts) if texts else "Tool returned isError=true")

        parts = []
        for content in result.content:
            if hasattr(content, "text"):
                parts.append(content.text)
            else:
                parts.append(str(content))
        return "\n".join(parts) if parts else ""

    def get_status(self) -> ServerStatus:
        return ServerStatus(
            server_id=self._config.id,
            status=self._status,
            error_message=self._error_message,
            tool_count=len(self._tools),
            last_connected_at=self._last_connected_at,
        )

    def get_tools(self) -> List[ToolDefinition]:
        return list(self._tools)

    # ── Internal ────────────────────────────────────────────────────────────

    async def _run_with_reconnect(self) -> None:
        """Run the session, reconnecting on unexpected failures."""
        attempt = 0
        while not self._stop_event.is_set():
            try:
                await self._run_session()
            except asyncio.CancelledError:
                return
            except Exception as e:
                if self._stop_event.is_set():
                    return
                self._status = ConnectionStatus.ERROR
                self._error_message = str(e)
                logger.error(f"MCP '{self._config.name}' error: {e}")

                if not self._ready_event.is_set():
                    self._ready_event.set()
                    return

                if not self._reconnect_enabled or attempt >= len(_RECONNECT_DELAYS):
                    logger.warning(
                        f"MCP '{self._config.name}' giving up after {attempt} reconnect attempts"
                    )
                    return

                delay = _RECONNECT_DELAYS[attempt]
                attempt += 1
                logger.info(
                    f"MCP '{self._config.name}' reconnecting in {delay}s (attempt {attempt})…"
                )
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=delay)
                except asyncio.TimeoutError:
                    pass

    async def _run_session(self) -> None:
        """Open transport + session, wait until stopped or transport drops."""
        cfg = self._config

        if cfg.transport == "stdio":
            import os
            merged_env = os.environ.copy()
            if cfg.env:
                merged_env.update(cfg.env)
            params = StdioServerParameters(
                command=cfg.command,
                args=cfg.args or [],
                env=merged_env,
            )
            async with stdio_client(params) as (read, write):
                await self._run_client_session(read, write)

        elif cfg.transport == "sse":
            async with sse_client(
                cfg.url,
                headers=cfg.headers or None,
                sse_read_timeout=300,
            ) as (read, write):
                await self._run_client_session(read, write)

        elif cfg.transport == "http":
            async with streamablehttp_client(
                cfg.url,
                headers=cfg.headers or None,
            ) as (read, write, get_session_id):
                await self._run_client_session(read, write, get_session_id)

        else:
            raise MCPConnectionError(f"Unknown transport: {cfg.transport}")

    @property
    def session_id(self) -> Optional[str]:
        """The transport-level session ID (available for streamable-HTTP connections)."""
        return self._session_id

    async def _run_client_session(self, read, write, get_session_id=None) -> None:
        """Initialise the ClientSession, cache tools, signal ready, then wait."""
        async with ClientSession(read, write) as session:
            self._session = session

            try:
                result = await session.initialize()
                proto = getattr(result, "protocolVersion", "unknown")
                if proto != "2024-11-05":
                    logger.warning(
                        f"MCP '{self._config.name}' returned protocolVersion={proto!r} "
                        "(expected 2024-11-05 — continuing anyway)"
                    )
            except Exception as e:
                raise MCPConnectionError(f"initialize failed: {e}") from e

            # Capture transport session ID (streamable-HTTP only)
            if callable(get_session_id):
                try:
                    self._session_id = get_session_id()
                except Exception:
                    pass

            try:
                tools_result = await session.list_tools()
                self._tools = [
                    ToolDefinition(
                        server_id=self._config.id,
                        server_name=self._config.name,
                        tool_id=f"{self._config.id}/{t.name}",
                        name=t.name,
                        description=t.description or "",
                        input_schema=t.inputSchema if isinstance(t.inputSchema, dict) else {},
                    )
                    for t in tools_result.tools
                ]
            except Exception as e:
                raise MCPConnectionError(f"tools/list failed: {e}") from e

            self._status = ConnectionStatus.CONNECTED
            self._last_connected_at = datetime.now(timezone.utc).isoformat()
            self._ready_event.set()
            logger.info(
                f"MCP '{self._config.name}' connected — {len(self._tools)} tool(s) discovered"
            )

            await self._stop_event.wait()

        self._session = None
