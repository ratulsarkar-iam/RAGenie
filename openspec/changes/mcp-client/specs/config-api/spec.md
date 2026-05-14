# Spec: config-api

## Purpose

REST API for full CRUD of MCP server configurations plus runtime connect/disconnect, tool listing, connection testing, and Claude Desktop JSON import/export — all changes taking effect immediately at runtime.

## Module

`src/api/mcp_client_routes.py`

Mounted in `app.py` with prefix `/api` (no extra prefix — routes already start with `/api/mcp-servers`).

> **Route registration order**: Static routes (`/import`, `/export`) MUST be registered **before** parameterised routes (`/{id}`, `/{id}/connect`, etc.) in this file. FastAPI matches routes in declaration order; registering `/{id}` first causes `GET /api/mcp-servers/export` to be captured with `id="export"` and return 404.

---

## Endpoints

### List Servers
```
GET /api/mcp-servers
```
Returns all configured servers (connected or not) with their current status and tool count.

**Response 200**
```json
[
  {
    "config": {
      "id": "abc123",
      "name": "filesystem",
      "transport": "stdio",
      "enabled": true,
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/Users/me/Documents"],
      "env": null,
      "url": null,
      "created_at": "2025-05-12T10:00:00Z",
      "updated_at": "2025-05-12T10:00:00Z"
    },
    "status": {
      "server_id": "abc123",
      "status": "connected",
      "error_message": null,
      "tool_count": 8,
      "last_connected_at": "2025-05-12T10:01:00Z"
    },
    "tools": []
  }
]
```
Note: `env` is **omitted** (null) in list responses for security. Use `GET /api/mcp-servers/{id}` to retrieve env vars in the editor context.

---

### Create Server
```
POST /api/mcp-servers
```
**Request body** (`ServerConfigCreate`):
```json
{
  "name": "github",
  "transport": "stdio",
  "enabled": true,
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-github"],
  "env": { "GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_xxx" },
  "connect_now": true
}
```
`connect_now` (default `true`): if `true` and `enabled=true`, immediately attempt connection after creation.

**Response 201**: full `ServerWithStatus` (including `env` since this is the creation response).

**Error 400**: validation failure (e.g. `stdio` without `command`, duplicate name).

---

### Get Server
```
GET /api/mcp-servers/{id}
```
Returns full `ServerWithStatus` including `env` and full `tools` list.

**Response 404** if not found.

---

### Update Server
```
PATCH /api/mcp-servers/{id}
```
**Request body** (`ServerConfigPatch`): any subset of fields.

Behaviour:
- Config is updated in DB.
- If the server is currently connected, it is disconnected and reconnected with the new config.
- If `enabled` is set to `false`, the server is disconnected and not reconnected.

**Response 200**: updated `ServerWithStatus`.

---

### Delete Server
```
DELETE /api/mcp-servers/{id}
```
- Disconnects if connected.
- Removes from DB.

**Response 204** on success. **Response 404** if not found.

---

### Connect Server
```
POST /api/mcp-servers/{id}/connect
```
Connects (or reconnects) the server. Uses the config currently in DB.

**Response 200**:
```json
{
  "server_id": "abc123",
  "status": "connected",
  "tool_count": 8,
  "last_connected_at": "2025-05-12T10:01:00Z"
}
```
**Response 400** if connection fails (error message included).

---

### Disconnect Server
```
POST /api/mcp-servers/{id}/disconnect
```
Gracefully disconnects. Does not delete from DB.

**Response 200**: `ServerStatus` with `status: "disconnected"`.

---

### List Server Tools
```
GET /api/mcp-servers/{id}/tools
```
Returns the last-known tool list for the server (from the in-memory registry).

**Response 200**:
```json
[
  {
    "server_id": "abc123",
    "server_name": "filesystem",
    "tool_id": "abc123/read_file",
    "name": "read_file",
    "description": "Read the contents of a file at the given path",
    "input_schema": { "type": "object", "properties": { "path": { "type": "string" } }, "required": ["path"] }
  }
]
```
**Response 404** if server not found. **Response 409** if server is not connected (empty list with message).

---

### Test Connection
```
POST /api/mcp-servers/{id}/test
```
Performs an ephemeral connect → `tools/list` → disconnect sequence to verify the config works.

**Response 200** (success):
```json
{
  "success": true,
  "tool_count": 8,
  "tools": [ ... ],
  "latency_ms": 243
}
```
**Response 200** (failure — still 200, error is in body):
```json
{
  "success": false,
  "error": "FileNotFoundError: npx not found"
}
```

---

### Import from Claude Desktop JSON
```
POST /api/mcp-servers/import
Content-Type: application/json
```
**Request body**:
```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
      "env": {}
    },
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": { "GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_xxx" }
    }
  },
  "connect_now": false
}
```
Upsert behaviour: if a server with the same `name` already exists, it is updated; otherwise created.

**Response 200**:
```json
{
  "created": 1,
  "updated": 1,
  "skipped": 0
}
```

---

### Export to Claude Desktop JSON
```
GET /api/mcp-servers/export
```
Returns all `stdio` servers in Claude Desktop-compatible format. `sse` servers are included as a custom `"url"` key (not part of the official Claude Desktop schema, but harmless).

**Response 200**:
```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
      "env": {}
    }
  }
}
```

---

## Request/Response Models (Pydantic)

> **Layer separation**: `ServerConfigCreate` and `ServerConfigPatch` are defined in `src/mcp_client/server_store.py` (store layer, no `connect_now`). The API layer extends `ServerConfigCreate` with the `connect_now` field:

```python
# Store-layer models (defined in server_store.py, imported here)
# ServerConfigCreate: name, transport, enabled, command, args, env, url
# ServerConfigPatch:  all-optional version of the above

# API layer extension — adds connect_now (not persisted)
class ServerCreateRequest(ServerConfigCreate):
    connect_now: bool = True

class ServerConfigPatch(BaseModel):              # store layer (shown for reference)
    name: Optional[str] = None
    transport: Optional[Literal["stdio", "sse"]] = None
    enabled: Optional[bool] = None
    command: Optional[str] = None
    args: Optional[List[str]] = None
    env: Optional[Dict[str, str]] = None
    url: Optional[str] = None

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
```

---

## Error Codes

| HTTP | Condition |
|------|-----------|
| 400 | Validation failure (missing required field, duplicate name, bad URL) |
| 404 | Server `id` not found |
| 409 | Operation not allowed in current state (e.g. tools requested while disconnected) |
| 500 | Unexpected internal error |

---

## Tests (`tests/test_mcp_client_api.py`)

- `GET /api/mcp-servers` returns list with correct status shapes
- `POST /api/mcp-servers` creates and returns 201; duplicate name returns 400
- `PATCH /api/mcp-servers/{id}` updates DB and triggers reload
- `DELETE /api/mcp-servers/{id}` removes from DB and disconnects
- `POST /api/mcp-servers/{id}/connect` returns connected status on success; 400 on failure
- `POST /api/mcp-servers/{id}/test` returns tool list on success; `success: false` on bad config
- `POST /api/mcp-servers/import` with valid Claude Desktop JSON creates/updates correctly
- `GET /api/mcp-servers/export` returns correct JSON shape
