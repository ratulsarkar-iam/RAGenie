# Spec: mcp-server-isolation

## Purpose

Scope MCP server configurations and their live tool registries/connections by `user_id`, so that each user's connected MCP servers and discovered tools are private and never leak into another user's chat/tool-call context.

## Modules

- `src/mcp_client/server_store.py` (modified — `user_id` scoping)
- `src/mcp_client/manager.py` (unchanged internally — one instance per user now, instead of one global instance)
- `src/mcp_client/multi_user_manager.py` (new — `MultiUserMCPManagerRegistry`)
- `src/api/mcp_client_routes.py` (modified — auth + per-user manager resolution)
- `src/chat/orchestrator.py` (modified — resolves per-user manager for tool listing/dispatch)

## Database

```sql
CREATE TABLE IF NOT EXISTS mcp_servers (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL,
    name        TEXT NOT NULL,
    transport   TEXT NOT NULL CHECK(transport IN ('stdio', 'sse', 'http')),
    enabled     INTEGER NOT NULL DEFAULT 1,
    command     TEXT,
    args        TEXT,
    env         TEXT,
    url         TEXT,
    headers     TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    UNIQUE(user_id, name)
);
CREATE INDEX IF NOT EXISTS idx_mcp_servers_user ON mcp_servers(user_id);
```

Legacy DBs: `user_id` added via guarded `ALTER TABLE`, same pattern as the existing `headers` column migration in `server_store.py:64-68`. Uniqueness for `(user_id, name)` enforced at the application layer for pre-existing databases (SQLite limitation, same as `keyword-isolation`).

## Public Interface

```python
class ServerConfigStore:
    def create(self, user_id: str, data: ServerConfigCreate) -> ServerConfig: ...
    def get(self, server_id: str) -> Optional[ServerConfig]: ...        # caller checks ownership
    def get_by_name(self, user_id: str, name: str) -> Optional[ServerConfig]: ...
    def list(self, user_id: str) -> List[ServerConfig]: ...
    def update(self, server_id: str, patch: ServerConfigPatch) -> ServerConfig: ...
    def delete(self, server_id: str) -> bool: ...

class MultiUserMCPManagerRegistry:
    async def get_or_create(self, user_id: str) -> MCPClientManager: ...
    async def shutdown_all(self) -> None: ...
```

`MCPClientManager` itself (`src/mcp_client/manager.py`) is unchanged — it already encapsulates its own `_connections`/`_registry`/`_llm_name_map` per instance; the only change is that the app now creates **one instance per user** via the registry instead of one process-wide singleton.

## Behavior

- On first use per user (first MCP-related API call or first chat message needing tools), `MultiUserMCPManagerRegistry.get_or_create(user_id)` lazily instantiates a `MCPClientManager` scoped to that user's `ServerConfigStore` view and connects that user's enabled servers.
- `ChatOrchestrator`'s tool-building step resolves the manager for the requesting user before merging tools into the LLM's tool list — no cross-user tool visibility.
- `ChatOrchestrator`'s tool-dispatch step routes `server_name/tool_name` calls through that same per-user manager.
- Shutdown: `registry.shutdown_all()` gracefully disconnects every user's connections on app shutdown.

## API

```
GET    /api/mcp-servers                 (auth) → registry manager for current_user; list_servers_with_status()
POST   /api/mcp-servers                 (auth) → create(current_user.id, body) in store; optionally connect via manager
GET    /api/mcp-servers/{id}            (auth) → 404 if not owned
PATCH  /api/mcp-servers/{id}            (auth) → 404 if not owned, else update + reload if connected
DELETE /api/mcp-servers/{id}            (auth) → 404 if not owned, else disconnect + delete
POST   /api/mcp-servers/{id}/connect    (auth) → 404 if not owned
POST   /api/mcp-servers/{id}/disconnect (auth) → 404 if not owned
GET    /api/mcp-servers/{id}/tools      (auth) → 404 if not owned
POST   /api/mcp-servers/{id}/test       (auth) → 404 if not owned
```

Route paths/shapes are unchanged from the existing single-tenant API — only manager/store resolution changes.

## Error Behavior

- `404 Not Found` on any reference to a `server_id` not owned by the requester.
- `409 Conflict` on creating a `name` the same user already has (different users may reuse the same server name).

## Tests (`tests/test_mcp_server_isolation.py`)

- User A creates server "srv1"; user B creates server "srv1" too — both succeed independently.
- User A's `list_all_tools()` (via their manager) never includes user B's tools.
- User A cannot `connect`/`disconnect`/`delete` user B's server id — `404`.
- Chat tool-call dispatch for user A only ever reaches user A's connected servers.
- `registry.shutdown_all()` disconnects all per-user managers cleanly.
