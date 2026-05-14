# MCP Client Module — Implementation Tasks

## Phase 1: Foundation — Data Models & Config Store (Week 1)

### 1.1 Package Scaffold
- [ ] Create `src/mcp_client/` package with `__init__.py`
- [ ] Add Pydantic models to `src/mcp_client/models.py`:
  - `ServerConfig`, `ConnectionStatus` (enum), `ServerStatus`, `ToolDefinition`, `ServerWithStatus`
- [ ] Add `MCPClientConfig(BaseModel)` to `src/config/models.py`:
  ```python
  class MCPClientConfig(BaseModel):
      store_path: str = Field(default="data/mcp_client/servers.db")
  ```
- [ ] Add `mcp_client: MCPClientConfig` field to the root `Config` model in `src/config/models.py`
- [ ] Add `mcp_client` block to `config/config.yaml`:
  ```yaml
  mcp_client:
    store_path: "data/mcp_client/servers.db"
  ```

### 1.2 Server Config Store
- [ ] Implement `src/mcp_client/server_store.py` — `ServerConfigStore`
  - `create(config: ServerConfigCreate) -> ServerConfig`
  - `get(id: str) -> Optional[ServerConfig]`
  - `get_by_name(name: str) -> Optional[ServerConfig]`
  - `list() -> List[ServerConfig]`
  - `update(id: str, patch: ServerConfigPatch) -> ServerConfig`
  - `delete(id: str) -> bool`
  - `migrate_from_yaml(mcp_clients: List[MCPClientServerConfig]) -> int`
- [ ] Write unit tests: `tests/test_mcp_client_store.py`

---

## Phase 2: Transport Layer (Week 1–2)

### 2.1 Abstract Transport Interface
- [ ] Add `httpx` to `requirements.txt` (needed for `SSETransport`)
- [ ] Implement `src/mcp_client/transport.py`:
  - `BaseTransport` — abstract class with `send(rpc: dict)`, `receive() -> dict`, `connect()`, `disconnect()`, `is_connected() -> bool`
  - `StdioTransport` — launches subprocess, communicates via stdin/stdout newline-delimited JSON
    - `command: str`, `args: List[str]`, `env: Optional[dict]`
    - Non-blocking reads using `asyncio.create_subprocess_exec`
    - Graceful `SIGTERM` on disconnect; SIGKILL fallback after 5 s
  - `SSETransport` — connects to HTTP SSE endpoint, POSTs messages to `/messages?sessionId=...`
    - Uses `httpx.AsyncClient` with SSE streaming
    - Reads `event: endpoint` to discover the POST URL
    - Buffers incoming SSE `event: message` frames and resolves pending RPC futures by `id`

### 2.2 Transport Tests
- [ ] Write unit tests: `tests/test_mcp_transport.py`
  - Mock subprocess for stdio
  - Mock HTTP server for SSE (use `pytest-httpx` or `respx`)

---

## Phase 3: MCP Client Connection (Week 2)

### 3.1 MCPClientConnection
- [ ] Implement `src/mcp_client/client.py` — `MCPClientConnection`
  - Constructor: takes `ServerConfig`, builds transport
  - `connect() -> None`:
    1. `transport.connect()`
    2. Send `initialize` RPC; if `protocolVersion` != `"2024-11-05"`, log WARNING and continue
    3. Send `initialized` notification
    4. Send `tools/list`; cache `List[ToolDefinition]`
    5. Set `status = CONNECTED`
  - `disconnect() -> None`: clean teardown, `status = DISCONNECTED`
  - `call_tool(name: str, args: dict) -> str`: sends `tools/call`, returns content text
  - `get_status() -> ServerStatus`
  - `get_tools() -> List[ToolDefinition]`
  - Auto-reconnect: on unexpected disconnect, retry with back-off (10 s / 30 s / 60 s, max 3 attempts)
- [ ] Write unit tests: `tests/test_mcp_client_connection.py`

---

## Phase 4: Client Manager (Week 2)

### 4.1 MCPClientManager
- [ ] Implement `src/mcp_client/manager.py` — `MCPClientManager`
  - Constructor: takes `ServerConfigStore`
  - Internal state: `_connections: Dict[server_id, MCPClientConnection]`, `_registry: Dict[tool_id, (conn, ToolDefinition)]`, `_llm_name_map: Dict[llm_name, tool_id]`
  - `initialize_all() -> None`: load all `enabled=True` configs, call `connect_server()` for each
  - `connect_server(config: ServerConfig) -> None`: create `MCPClientConnection`, connect, register tools in both `_registry` and `_llm_name_map`
  - `disconnect_server(server_id: str) -> None`: disconnect, remove entries from `_registry` and `_llm_name_map`, remove connection
  - `reload_server(server_id: str) -> None`: disconnect + reconnect; raise `KeyError` if `store.get(server_id)` returns `None`
  - `list_servers_with_status() -> List[ServerWithStatus]`
  - `get_server_status(server_id: str) -> ServerStatus`
  - `list_all_tools() -> List[ToolDefinition]`: flat list across all connected servers
  - `call_tool(llm_tool_name: str, args: dict) -> str`: resolve via `_llm_name_map` → dispatch via `_registry`; raise `KeyError` if not found
  - `shutdown() -> None`: disconnect all connections
- [ ] Write unit tests: `tests/test_mcp_client_manager.py`
  - Happy path: two servers, both tools registered in both maps
  - `call_tool("filesystem/read_file", ...)` resolves correctly
  - Disconnect removes entries from both maps
  - Two servers with identically-named tool (e.g. `search`): both appear under different LLM names

---

## Phase 5: Orchestrator Integration (Week 2–3)

### 5.1 Modify ChatOrchestrator
- [ ] Add optional `mcp_client_manager: Optional[MCPClientManager]` parameter to `ChatOrchestrator.__init__`
- [ ] In the tool-building step: append `mcp_client_manager.list_all_tools()` to the tool list passed to the LLM
- [ ] In the tool-dispatch step: if tool name contains `/`, it is a `server_name/tool_name` LLM-facing name — route to `mcp_client_manager.call_tool(llm_tool_name, args)` (manager resolves via `_llm_name_map` internally)
- [ ] Gracefully handle `MCPClientManager` being `None` (backward-compatible; no external MCP tools are shown)
- [ ] Write integration test: `tests/test_orchestrator_mcp_integration.py`

### 5.2 Wire into app.py Startup
- [ ] Instantiate `ServerConfigStore` in `startup_event`
- [ ] Call `store.migrate_from_yaml(config.mcp_clients)` on first run
- [ ] Instantiate `MCPClientManager(store)` and call `initialize_all()`
- [ ] Pass manager to `ChatOrchestrator`
- [ ] Add manager to `app_state["mcp_client_manager"]`
- [ ] Call `manager.shutdown()` in `shutdown_event`

---

## Phase 6: Config API (Week 3)

### 6.1 REST Router
- [ ] Implement `src/api/mcp_client_routes.py`:
  - **Register static routes FIRST, then `/{id}` routes** (FastAPI ordering constraint)
  - `GET  /api/mcp-servers` → `list_servers()`: returns `List[ServerWithStatus]`
  - `POST /api/mcp-servers` → `create_server(body: ServerCreateRequest)`: creates + optionally connects
  - `POST /api/mcp-servers/import` → `import_servers(body)`: parse Claude Desktop JSON, bulk upsert ← register BEFORE `/{id}`
  - `GET  /api/mcp-servers/export` → `export_servers()`: return Claude Desktop-compatible JSON ← register BEFORE `/{id}`
  - `GET  /api/mcp-servers/{id}` → `get_server(id)`: returns `ServerWithStatus`
  - `PATCH /api/mcp-servers/{id}` → `update_server(id, patch)`: update config; if connected, reload
  - `DELETE /api/mcp-servers/{id}` → `delete_server(id)`: disconnect + delete from DB
  - `POST /api/mcp-servers/{id}/connect` → `connect_server(id)`: connect or reconnect
  - `POST /api/mcp-servers/{id}/disconnect` → `disconnect_server(id)`: disconnect
  - `GET  /api/mcp-servers/{id}/tools` → `list_server_tools(id)`: list discovered tools
  - `POST /api/mcp-servers/{id}/test` → `test_server(id)`: ephemeral connect → list tools → disconnect; returns tools or error
- [ ] Access `app_state["mcp_client_manager"]` via `_get_manager()` helper (503 if not initialised)
- [ ] Include `mcp_client_router` in `app.py`
- [ ] Write API integration tests: `tests/test_mcp_client_api.py`

---

## Phase 7: Frontend — Settings Page (Week 4)

### 7.1 API Client
- [ ] Add `frontend/src/api/mcpClientApi.ts`:
  - `listServers()`, `createServer()`, `getServer()`, `updateServer()`, `deleteServer()`
  - `connectServer()`, `disconnectServer()`, `listServerTools()`, `testServer()`
  - `importServers(json: string)`, `exportServers() -> string`

### 7.2 Settings Page Components
- [ ] Implement `frontend/src/components/MCPServersPage.tsx`:
  - Server list with status badges (connected ✅ / error ⚠ / disconnected ○)
  - Tool count per server
  - Actions: Add, Import JSON, Export JSON
  - Click a server to open the editor panel
- [ ] Implement `frontend/src/components/MCPServerEditor.tsx`:
  - Form fields: name, transport (dropdown), command, args (tag input), env vars (key-value list), url
  - Enabled/disabled toggle
  - [Connect], [Disconnect], [Refresh Tools], [Save], [Delete] actions
  - Inline error banner for connection failures
- [ ] Implement `frontend/src/components/MCPToolBrowser.tsx`:
  - Accordion list of tools for the selected server
  - Each tool: name (bold), description, input schema badge (hover to expand)
- [ ] Implement `frontend/src/components/MCPImportExportModal.tsx`:
  - Textarea for pasting/copying Claude Desktop JSON
  - Validate JSON on paste; show parse error inline
  - [Import] button: calls `importServers()` then refreshes list
- [ ] Add "MCP Servers" nav item to the Settings section in `App.tsx`
- [ ] Poll `GET /api/mcp-servers` every 10 s to refresh connection statuses

### 7.3 Chat Integration Indicator
- [ ] In the chat input area, add a small "🔌 N tools" badge that shows total tool count (built-in + external MCP)
- [ ] Clicking the badge opens a tool browser overlay (reuse `MCPToolBrowser`)

---

## Phase 8: Polish & Tests (Week 4–5)

- [ ] End-to-end test: start a local `@modelcontextprotocol/server-filesystem` process, add it via API, verify:
  - Tools appear in `GET /api/mcp-servers/{id}/tools`
  - LLM tool list contains `"filesystem/read_file"` (not UUID-prefixed)
  - Tool call via WebSocket chat path succeeds end-to-end
- [ ] Add `mcp_client.store_path` to `config/config.yaml` documentation comments
- [ ] Update `README.md`: MCP Client section with quick-start guide and Claude Desktop config migration instructions
- [ ] Deprecate old `MCPManager` / `MCPClient` in `src/tasks/mcp_manager.py` (keep for backward compat, add `DeprecationWarning` log on init)
- [ ] Confirm `httpx` is in `requirements.txt` (added in Phase 2; this is a final check)
