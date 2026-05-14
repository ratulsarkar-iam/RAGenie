# Spec: server-store

## Purpose

Persistent SQLite-backed store for MCP server configurations. Provides live CRUD without requiring a config-file edit or restart. Handles one-time migration of existing `config.yaml` `mcp_clients` entries on first boot.

## Module

`src/mcp_client/server_store.py`

## Database

Path: `data/mcp_client/servers.db` (configurable via `config.mcp_client.store_path`)

```sql
CREATE TABLE IF NOT EXISTS mcp_servers (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    transport   TEXT NOT NULL CHECK(transport IN ('stdio', 'sse')),
    enabled     INTEGER NOT NULL DEFAULT 1,
    command     TEXT,
    args        TEXT,          -- JSON array string, e.g. '["npx","-y","@mcp/server-fs"]'
    env         TEXT,          -- JSON object string, e.g. '{"API_KEY":"..."}'
    url         TEXT,
    created_at  TEXT NOT NULL, -- ISO-8601 UTC
    updated_at  TEXT NOT NULL  -- ISO-8601 UTC
);
```

## Public Interface

```python
class ServerConfigCreate(BaseModel):
    name: str
    transport: Literal["stdio", "sse"]
    enabled: bool = True
    command: Optional[str] = None
    args: Optional[List[str]] = None
    env: Optional[Dict[str, str]] = None
    url: Optional[str] = None

class ServerConfigPatch(BaseModel):
    name: Optional[str] = None
    transport: Optional[Literal["stdio", "sse"]] = None
    enabled: Optional[bool] = None
    command: Optional[str] = None
    args: Optional[List[str]] = None
    env: Optional[Dict[str, str]] = None
    url: Optional[str] = None

class ServerConfigStore:
    def __init__(self, db_path: str): ...

    def create(self, data: ServerConfigCreate) -> ServerConfig: ...
    def get(self, id: str) -> Optional[ServerConfig]: ...
    def get_by_name(self, name: str) -> Optional[ServerConfig]: ...
    def list(self) -> List[ServerConfig]: ...
    def update(self, id: str, patch: ServerConfigPatch) -> ServerConfig: ...
    def delete(self, id: str) -> bool: ...

    def migrate_from_yaml(
        self,
        mcp_clients: List[MCPClientServerConfig]
    ) -> int:
        """
        For each entry in mcp_clients that does NOT already exist in the DB
        (matched by name), insert it.
        Returns the count of newly inserted rows.
        Called once from app startup_event.
        """
```

## Validation Rules

- `name` must be non-empty and unique.
- `transport == "stdio"` requires `command` to be non-empty.
- `transport == "sse"` requires `url` to be a valid `http://` or `https://` URL.
- `args` and `env` are serialised as JSON strings in SQLite; deserialised on read.

## Error Behaviour

- `create` with a duplicate `name` raises `ValueError("name already exists")`.
- `get` / `update` / `delete` on a non-existent `id` raise `KeyError`.
- All DB operations use a context-manager connection; exceptions roll back automatically.

## Tests (`tests/test_mcp_client_store.py`)

- CRUD happy path (create → list → get → update → delete)
- Duplicate name raises `ValueError`
- `migrate_from_yaml`: new entries are inserted; existing entries are skipped
- JSON serialisation round-trip for `args` and `env`
