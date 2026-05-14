"""MCPClientManager — manages all MCP server connections and the unified tool registry."""
import asyncio
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from .client import MCPClientConnection
from .exceptions import MCPConnectionError, MCPToolError
from .models import (
    ConnectionStatus, ServerConfig, ServerStatus, ServerWithStatus, ToolDefinition,
)
from .server_store import ServerConfigStore
from ..core.logging_config import get_logger

logger = get_logger(__name__)


class MCPClientManager:
    """
    Owns a dict of active MCPClientConnections.
    Maintains two parallel lookup structures:
      _registry:     {server_id/tool_name → (conn, ToolDefinition)}   — internal dispatch key
      _llm_name_map: {server_name/tool_name → server_id/tool_name}    — LLM-visible name → internal key
    """

    def __init__(self, store: ServerConfigStore):
        self._store = store
        self._connections: Dict[str, MCPClientConnection] = {}
        self._registry: Dict[str, Tuple[MCPClientConnection, ToolDefinition]] = {}
        self._llm_name_map: Dict[str, str] = {}
        self._on_tools_changed: Optional[Callable[[], None]] = None
        self._session_meta: Dict[str, Dict[str, Any]] = {}  # server_id → arbitrary session state

    def set_tools_changed_callback(self, callback: Callable[[], None]) -> None:
        """Register a callback invoked whenever the tool registry changes."""
        self._on_tools_changed = callback

    # ── Lifecycle ────────────────────────────────────────────────────────────

    @staticmethod
    def _is_localhost_url(config: "ServerConfig") -> bool:
        """Return True if this is an HTTP/SSE server pointing at localhost."""
        url = getattr(config, "url", None) or ""
        return bool(url) and any(
            h in url for h in ("localhost", "127.0.0.1", "0.0.0.0", "::1")
        )

    async def initialize_all(self) -> None:
        """Connect all enabled servers from the store on startup.

        Localhost HTTP servers are deferred by 10 s so that any in-process MCP
        server (e.g. port 8001) has time to start before we try to connect.
        """
        configs = self._store.list()
        enabled = [c for c in configs if c.enabled]
        if not enabled:
            logger.info("No enabled MCP servers configured")
            return

        remote = [c for c in enabled if not self._is_localhost_url(c)]
        local  = [c for c in enabled if self._is_localhost_url(c)]

        results = await asyncio.gather(
            *[self._connect_single(c) for c in remote],
            return_exceptions=True,
        )
        ok = sum(1 for r in results if not isinstance(r, Exception))

        if local:
            async def _deferred_connect_local():
                await asyncio.sleep(10)
                for c in local:
                    try:
                        await self._connect_single(c)
                        logger.info(f"Deferred connect to local MCP server '{c.name}' succeeded")
                    except Exception as e:
                        logger.warning(f"Deferred connect to local MCP server '{c.name}' failed: {e}")

            asyncio.create_task(_deferred_connect_local())
            logger.info(
                f"MCP manager: {ok}/{len(remote)} remote server(s) connected; "
                f"{len(local)} local server(s) deferred 10 s"
            )
        else:
            logger.info(f"MCP manager: {ok}/{len(enabled)} server(s) connected")

    async def connect_server(self, config: ServerConfig) -> None:
        """Connect (or reconnect) a single server. Updates the tool registry."""
        if config.id in self._connections:
            await self.disconnect_server(config.id)
        await self._connect_single(config)

    async def _connect_single(self, config: ServerConfig) -> None:
        conn = MCPClientConnection(config)
        try:
            await conn.connect()
        except Exception as e:
            logger.error(f"Could not connect to MCP server '{config.name}': {e}")
            raise
        self._connections[config.id] = conn
        self._register_tools(config.id, conn)
        self._notify_tools_changed()

    async def disconnect_server(self, server_id: str) -> None:
        """Disconnect a server and remove its tools from the registry."""
        conn = self._connections.pop(server_id, None)
        if conn:
            await conn.disconnect()
        self._deregister_tools(server_id)
        self._session_meta.pop(server_id, None)  # clear session on disconnect
        self._notify_tools_changed()

    async def reload_server(self, server_id: str) -> None:
        """Disconnect then reconnect with the latest config from the store."""
        config = self._store.get(server_id)
        if config is None:
            raise KeyError(f"Server not found: {server_id}")
        await self.disconnect_server(server_id)
        if config.enabled:
            await self._connect_single(config)

    async def shutdown(self) -> None:
        """Gracefully disconnect all servers."""
        ids = list(self._connections.keys())
        await asyncio.gather(
            *[self.disconnect_server(sid) for sid in ids],
            return_exceptions=True,
        )
        logger.info("MCP client manager shut down")

    # ── Session metadata ──────────────────────────────────────────────────────

    def set_session_meta(self, server_id: str, key: str, value: Any) -> None:
        """Store arbitrary session state for a server (e.g. logged_in=True)."""
        self._session_meta.setdefault(server_id, {})[key] = value

    def get_session_meta(self, server_id: str) -> Dict[str, Any]:
        return dict(self._session_meta.get(server_id, {}))

    def server_id_for_name(self, server_name: str) -> Optional[str]:
        """Resolve a server_name (e.g. 'KITE') to its server_id."""
        for config in self._store.list():
            if config.name == server_name:
                return config.id
        return None

    # ── Registry helpers ─────────────────────────────────────────────────────

    def _register_tools(self, server_id: str, conn: MCPClientConnection) -> None:
        for td in conn.get_tools():
            self._registry[td.tool_id] = (conn, td)
            llm_name = f"{td.server_name}/{td.name}"
            self._llm_name_map[llm_name] = td.tool_id

    def _deregister_tools(self, server_id: str) -> None:
        stale_tool_ids = {k for k in self._registry if k.startswith(f"{server_id}/")}
        for tid in stale_tool_ids:
            self._registry.pop(tid, None)
        stale_llm = [k for k, v in self._llm_name_map.items() if v in stale_tool_ids]
        for k in stale_llm:
            self._llm_name_map.pop(k, None)

    def _notify_tools_changed(self) -> None:
        if self._on_tools_changed:
            try:
                self._on_tools_changed()
            except Exception as e:
                logger.warning(f"tools_changed callback error: {e}")

    # ── Queries ──────────────────────────────────────────────────────────────

    def _with_session_meta(self, status: ServerStatus) -> ServerStatus:
        meta = self.get_session_meta(status.server_id)
        if meta:
            return status.model_copy(update={"session_meta": meta})
        return status

    def list_servers_with_status(self) -> List[ServerWithStatus]:
        results = []
        for config in self._store.list():
            conn = self._connections.get(config.id)
            if conn:
                status = self._with_session_meta(conn.get_status())
                tools = conn.get_tools()
            else:
                status = self._with_session_meta(ServerStatus(
                    server_id=config.id,
                    status=ConnectionStatus.DISCONNECTED,
                ))
                tools = []
            results.append(ServerWithStatus(config=config, status=status, tools=tools))
        return results

    def get_server_status(self, server_id: str) -> Optional[ServerStatus]:
        conn = self._connections.get(server_id)
        if conn:
            return self._with_session_meta(conn.get_status())
        config = self._store.get(server_id)
        if config:
            return self._with_session_meta(
                ServerStatus(server_id=server_id, status=ConnectionStatus.DISCONNECTED)
            )
        return None

    def list_all_tools(self) -> List[ToolDefinition]:
        """Flat list of all tools across all connected servers."""
        return [td for _, td in self._registry.values()]

    def get_llm_name_map(self) -> Dict[str, str]:
        """Returns {server_name/tool_name → server_id/tool_name}."""
        return dict(self._llm_name_map)

    # ── Tool dispatch ────────────────────────────────────────────────────────

    async def call_tool(self, llm_tool_name: str, args: dict) -> str:
        """
        Dispatch a tool call using the LLM-visible name (server_name/tool_name).
        Resolves via _llm_name_map then dispatches via _registry.
        """
        tool_id = self._llm_name_map.get(llm_tool_name)
        if tool_id is None:
            raise KeyError(f"MCP tool not found: '{llm_tool_name}'")

        conn, tool_def = self._registry[tool_id]
        bare_name = tool_def.name
        return await conn.call_tool(bare_name, args)

    def tool_count(self) -> int:
        return len(self._registry)
