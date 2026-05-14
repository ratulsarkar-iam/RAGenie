# Spec: tool-integration

## Purpose

Wire external MCP server tools into RAGenie's `MCPClientManager` tool registry and surface them to the `ChatOrchestrator` so the LLM can call them alongside built-in tools — with zero code changes needed when new servers are added or removed at runtime.

## Modules

- `src/mcp_client/manager.py` ← new
- `src/chat/orchestrator.py` ← modified

---

## MCPClientManager (`manager.py`)

```python
class MCPClientManager:
    def __init__(self, store: ServerConfigStore)

    async def initialize_all(self) -> None:
        """
        Load all enabled ServerConfigs from the store.
        For each, call connect_server(config).
        Failures are logged and skipped (startup is non-fatal per server).
        """

    async def connect_server(self, config: ServerConfig) -> None:
        """
        Create MCPClientConnection(config), call connection.connect().
        Register its tools in the flat tool registry.
        If a connection for config.id already exists, disconnect it first.
        """

    async def disconnect_server(self, server_id: str) -> None:
        """
        Call connection.disconnect().
        Remove all tools belonging to server_id from the registry.
        Remove connection from internal dict.
        """

    async def reload_server(self, server_id: str) -> None:
        """
        disconnect_server(server_id) then connect_server(store.get(server_id)).
        Used after a config PATCH.
        Raises KeyError if server_id is not found in the store.
        """

    def list_servers_with_status(self) -> List[ServerWithStatus]:
        """
        For every config in the store (connected or not), return ServerWithStatus.
        Servers not in the connections dict have status=DISCONNECTED.
        """

    def get_server_status(self, server_id: str) -> ServerStatus: ...

    def list_all_tools(self) -> List[ToolDefinition]:
        """Flat list of all tools across all currently connected servers."""

    async def call_tool(self, tool_id: str, args: dict) -> str:
        """
        tool_id format: "{server_id}/{tool_name}"
        Look up the connection from the registry.
        Delegate to connection.call_tool(tool_name, args).
        Raise KeyError if tool_id not found.
        """

    async def shutdown(self) -> None:
        """Disconnect all connections gracefully."""
```

### Tool Registry Structure

```python
# Internal registry — keyed by stable "{server_id}/{tool_name}" (used for dispatch)
_registry: Dict[str, Tuple[MCPClientConnection, ToolDefinition]]

# LLM name map — keyed by human-readable "{server_name}/{tool_name}" → internal tool_id
# e.g. "filesystem/read_file" → "abc123/read_file"
_llm_name_map: Dict[str, str]
```

Both maps are updated atomically whenever a server connects or disconnects.

Invariant: the registry is always consistent with the set of connected servers. When a server disconnects (including on error), all its entries are removed from both `_registry` and `_llm_name_map`.

`call_tool(llm_tool_name, args)` resolves via `_llm_name_map` first, then dispatches via `_registry`:
```python
async def call_tool(self, llm_tool_name: str, args: dict) -> str:
    tool_id = self._llm_name_map.get(llm_tool_name)
    if tool_id is None:
        raise KeyError(f"Tool not found: '{llm_tool_name}'")
    conn, _def = self._registry[tool_id]
    # Extract bare tool_name from tool_id for the MCP call
    tool_name = tool_id.split("/", 1)[1]
    return await conn.call_tool(tool_name, args)
```

---

## ChatOrchestrator Integration (`src/chat/orchestrator.py`)

### Constructor Change

```python
class ChatOrchestrator:
    def __init__(
        self,
        llm_wrapper,
        rag_store,
        search_service,
        max_history: int = 10,
        memory_manager=None,
        mcp_client_manager: Optional[MCPClientManager] = None,  # ← new
    ): ...
```

### Tool List Assembly

In the method that builds the tool list for the LLM (currently using `TOOLS` from `src/mcp/tools.py`):

```python
def _build_tool_list(self) -> List[dict]:
    tools = list(TOOLS)   # built-in RAGenie tools (search_documents, ask_ragenie, etc.)
    if self._mcp_client_manager:
        for td in self._mcp_client_manager.list_all_tools():
            # Use human-readable "server_name/tool_name" so the LLM can reason about it
            llm_name = f"{td.server_name}/{td.name}"   # e.g. "filesystem/read_file"
            tools.append({
                "name": llm_name,
                "description": f"[{td.server_name}] {td.description}",
                "inputSchema": td.input_schema,
            })
    return tools
```

> **Why `server_name/tool_name` and not UUID-prefixed `tool_id`**: The LLM reasons about tool names and must produce them verbatim in its output. A UUID prefix (`abc123/read_file`) is opaque and error-prone. `filesystem/read_file` is immediately interpretable. The `MCPClientManager._llm_name_map` resolves this back to the internal UUID-keyed `tool_id` at dispatch time.

### Tool Dispatch

In the method that executes a tool call requested by the LLM:

```python
async def _dispatch_tool(self, tool_name: str, args: dict) -> str:
    if "/" in tool_name:
        # External MCP tool — tool_name is "server_name/tool_name" (LLM-facing)
        if self._mcp_client_manager is None:
            return "Error: MCP client manager not available."
        try:
            # Manager resolves LLM name → internal tool_id → connection internally
            return await self._mcp_client_manager.call_tool(tool_name, args)
        except KeyError:
            return f"Error: tool '{tool_name}' not found (server may have disconnected)."
        except MCPToolError as e:
            return f"Tool error: {e}"
        except asyncio.TimeoutError:
            return f"Error: tool '{tool_name}' timed out."
    else:
        # Built-in RAGenie tool
        return await call_tool(tool_name, args)
```

> The `/` separator cleanly splits dispatch. Built-in tool names must never contain `/` (enforced by convention; all current names are snake_case without slashes).

### Backward Compatibility

If `mcp_client_manager=None` (default), the orchestrator behaves exactly as before. No existing tests break.

---

## Tool Naming Contract

| Source | `name` visible to LLM | Example |
|--------|----------------------|---------|
| Built-in RAGenie | plain string | `search_documents` |
| External MCP | `"{server_id}/{tool_name}"` | `abc123/read_file` |

The `/` separator is the dispatch signal. Built-in tool names must never contain `/`.

---

## app.py Wiring

```python
# In startup_event:
from ..mcp_client.server_store import ServerConfigStore
from ..mcp_client.manager import MCPClientManager

store = ServerConfigStore(config.mcp_client.store_path)
migrated = store.migrate_from_yaml(config.mcp_clients)
if migrated:
    logger.info(f"Migrated {migrated} MCP client config(s) from config.yaml to DB")

mcp_client_manager = MCPClientManager(store)
await mcp_client_manager.initialize_all()
app_state["mcp_client_manager"] = mcp_client_manager

orchestrator = ChatOrchestrator(
    ...,
    mcp_client_manager=mcp_client_manager,   # ← add
)

# In shutdown_event:
if app_state.get("mcp_client_manager"):
    await app_state["mcp_client_manager"].shutdown()
```

---

## WebSocket Path

The existing chat WebSocket handler (`src/api/websocket.py`) calls the same `ChatOrchestrator` instance. No changes are needed to `websocket.py` — once the orchestrator is updated with `mcp_client_manager`, the WebSocket chat path automatically gains access to external MCP tools. Verify this in the end-to-end test.

---

## Tests (`tests/test_orchestrator_mcp_integration.py`)

- Mock `MCPClientManager.list_all_tools()` returning two tool defs; verify LLM tool list contains `"filesystem/read_file"` (server_name-prefixed), NOT a UUID-prefixed name
- Mock `MCPClientManager.call_tool("filesystem/read_file", args)` returning a string; verify orchestrator returns it
- `mcp_client_manager=None`: tool list contains only built-in tools; no external dispatch attempted
- `call_tool` raises `KeyError`: orchestrator returns an error string, does not crash
- `call_tool` raises `asyncio.TimeoutError`: orchestrator returns timeout error string
- `list_all_tools()` with two servers that have tools of the same name (e.g. both have `search`): verify both appear as `server1/search` and `server2/search` without collision
