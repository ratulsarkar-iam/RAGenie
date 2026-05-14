# MCP Client Module — Design Document

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                      RAGenie Frontend (React)                       │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  Settings → MCP Servers Page                                  │  │
│  │  ┌──────────────────────┐  ┌────────────────────────────────┐ │  │
│  │  │  Server List         │  │  Server Editor                 │ │  │
│  │  │  (name, transport,   │  │  (form: name, transport,       │ │  │
│  │  │   status badge,      │  │   command/args/env or url,     │ │  │
│  │  │   tool count)        │  │   enabled toggle)              │ │  │
│  │  │                      │  │                                │ │  │
│  │  │  [+ Add Server]      │  │  [Tool Browser]                │ │  │
│  │  │  [Import JSON]       │  │  [Connect] [Disconnect]        │ │  │
│  │  │  [Export JSON]       │  │  [Test Connection]             │ │  │
│  │  └──────────────────────┘  └────────────────────────────────┘ │  │
│  └───────────────────────────────────────────────────────────────┘  │
└────────────────────────────┬────────────────────────────────────────┘
                             │  REST (axios)
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        FastAPI Backend                              │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  /api/mcp-servers  (mcp_client_routes.py)                     │  │
│  │  GET / POST / PATCH / DELETE / connect / disconnect / tools   │  │
│  └───────────────────────────┬───────────────────────────────────┘  │
│                              │                                      │
│  ┌───────────────────────────▼───────────────────────────────────┐  │
│  │  MCPClientManager  (src/mcp_client/manager.py)                │  │
│  │                                                               │  │
│  │  • Owns a dict[server_id → MCPClientConnection]               │  │
│  │  • Maintains unified tool registry: tool_id → (server, def)  │  │
│  │  • connect_server(cfg) / disconnect_server(id)                │  │
│  │  • call_tool(tool_id, args) → dispatches to right connection  │  │
│  │  • list_all_tools() → List[ToolDefinition]                    │  │
│  └──────────┬────────────────────────────────────────────────────┘  │
│             │                                                       │
│    ┌────────▼──────────┐          ┌────────────────────────┐       │
│    │  MCPClientConnection         │  MCPClientConnection   │       │
│    │  transport=stdio   │  · · ·  │  transport=sse         │       │
│    │  (StdioTransport)  │         │  (SSETransport)        │       │
│    └────────┬───────────┘         └────────────┬───────────┘       │
│             │                                  │                   │
│    ┌────────▼───────────────────────────────────▼─────────────┐    │
│    │  MCP JSON-RPC 2.0 Protocol Layer                         │    │
│    │  initialize → tools/list → tools/call                   │    │
│    └──────────────────────────────────────────────────────────┘    │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  ServerConfigStore  (src/mcp_client/server_store.py)          │  │
│  │  SQLite: mcp_servers table                                    │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  ChatOrchestrator  (src/chat/orchestrator.py)  ← modified     │  │
│  │  Injects MCPClientManager tools alongside built-in tools      │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                             │
          ┌──────────────────┼──────────────────────┐
          ▼                  ▼                       ▼
  ┌──────────────┐  ┌─────────────────┐   ┌──────────────────────┐
  │ Local stdio  │  │  Remote SSE     │   │   Any future MCP     │
  │ MCP server   │  │  MCP server     │   │   transport          │
  │ (e.g.        │  │  (e.g.          │   │                      │
  │  filesystem, │  │   mcp-server-   │   │                      │
  │  calendar)   │  │   github via    │   │                      │
  │              │  │   HTTP)         │   │                      │
  └──────────────┘  └─────────────────┘   └──────────────────────┘
```

## Module Breakdown

### New Package: `src/mcp_client/`

| Module | Responsibility |
|---|---|
| `__init__.py` | Package exports |
| `models.py` | Pydantic models: `ServerConfig`, `ServerStatus`, `ToolDefinition`, `ServerWithStatus` |
| `server_store.py` | SQLite CRUD for server configs; startup migration from `config.yaml` |
| `transport.py` | Abstract `BaseTransport`; `StdioTransport`; `SSETransport` |
| `client.py` | `MCPClientConnection`: wraps a transport, handles JSON-RPC handshake + tool calls |
| `manager.py` | `MCPClientManager`: lifecycle, tool registry, unified `call_tool()` |

### Modified: `src/api/`
- **New**: `mcp_client_routes.py` — FastAPI router for `/api/mcp-servers`

### Modified: `src/api/app.py`
- Instantiate `ServerConfigStore` and `MCPClientManager` at startup
- Connect all enabled servers on startup
- Wire shutdown disconnect
- Inject `mcp_client_manager` into `app_state`

### Modified: `src/chat/orchestrator.py`
- Accept optional `mcp_client_manager` dependency
- Merge external MCP tools into the tool list passed to the LLM
- Route `tools/call` for external tools through `mcp_client_manager.call_tool()`

### New Frontend: `frontend/src/`
- `api/mcpClientApi.ts` — typed API client
- `components/MCPServersPage.tsx` — main settings page
- `components/MCPServerEditor.tsx` — add/edit form
- `components/MCPToolBrowser.tsx` — discovered tools panel

---

## Data Models

```python
# src/mcp_client/models.py

class ServerConfig(BaseModel):
    id: str                                    # UUID
    name: str                                  # display name, e.g. "filesystem"
    transport: Literal["stdio", "sse"]
    enabled: bool = True

    # stdio-specific
    command: Optional[str] = None              # e.g. "npx"
    args: Optional[List[str]] = None           # e.g. ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
    env: Optional[Dict[str, str]] = None       # extra env vars (API keys etc.)

    # sse-specific
    url: Optional[str] = None                  # e.g. "http://localhost:8001/sse"

    created_at: datetime
    updated_at: datetime

class ConnectionStatus(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING   = "connecting"
    CONNECTED    = "connected"
    ERROR        = "error"

class ServerStatus(BaseModel):
    server_id: str
    status: ConnectionStatus
    error_message: Optional[str] = None
    tool_count: int = 0
    last_connected_at: Optional[datetime] = None

class ToolDefinition(BaseModel):
    server_id: str
    server_name: str
    tool_id: str                               # "{server_id}/{tool_name}" — unique across all servers
    name: str                                  # original MCP tool name
    description: str
    input_schema: dict

class ServerWithStatus(BaseModel):
    config: ServerConfig
    status: ServerStatus
    tools: List[ToolDefinition] = []
```

---

## Database Schema

```sql
-- mcp_servers table
CREATE TABLE mcp_servers (
    id          TEXT PRIMARY KEY,              -- UUID
    name        TEXT NOT NULL UNIQUE,
    transport   TEXT NOT NULL,                 -- "stdio" | "sse"
    enabled     INTEGER NOT NULL DEFAULT 1,
    command     TEXT,
    args        TEXT,                          -- JSON array
    env         TEXT,                          -- JSON object
    url         TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
```

---

## Transport Layer

### `StdioTransport`

Launches the MCP server as a subprocess. Communicates via stdin/stdout using newline-delimited JSON-RPC 2.0.

```
RAGenie                        External MCP server (subprocess)
   │                                      │
   │── stdin: {"jsonrpc":"2.0","id":1, ──▶│
   │          "method":"initialize",...}  │
   │                                      │
   │◀── stdout: {"jsonrpc":"2.0","id":1, ─│
   │            "result":{...}}           │
   │                                      │
   │── stdin: {"method":"tools/list",...}▶│
   │◀── stdout: {"result":{"tools":[...]}}│
```

### `SSETransport`

Connects to a running MCP server over HTTP. Uses SSE (Server-Sent Events) for server→client messages, and HTTP POST for client→server messages — matching the MCP SSE transport spec (`2024-11-05`).

```
RAGenie                        Remote MCP server (HTTP)
   │                                      │
   │── GET /sse ─────────────────────────▶│  (SSE stream opens)
   │◀── event: endpoint                   │
   │    data: /messages?sessionId=abc     │
   │                                      │
   │── POST /messages?sessionId=abc ─────▶│
   │    {"method":"initialize",...}       │
   │                                      │
   │◀── event: message ───────────────────│
   │    data: {"result":{...}}            │
```

---

## MCP JSON-RPC Handshake Sequence

```
1. Transport connects (subprocess launch or HTTP GET /sse)
2. Client sends:  initialize  { protocolVersion, clientInfo, capabilities }
3. Server sends:  initialize response { protocolVersion, serverInfo, capabilities }
4. Client sends:  initialized  (notification, no response)
5. Client sends:  tools/list
6. Server sends:  tools/list response { tools: [...] }
7. Tool definitions stored in MCPClientManager registry
8. [On tool call from LLM]
   Client sends:  tools/call { name, arguments }
   Server sends:  tools/call response { content: [{type, text}], isError }
```

---

## Tool Registry & LLM Integration

`MCPClientManager` maintains two parallel structures:

**Internal registry** (keyed by stable `server_id/tool_name` — used for dispatch):
```
{
  "abc123/read_file":     (server_conn, tool_def),
  "abc123/list_dir":      (server_conn, tool_def),
  "def456/github_search": (server_conn, tool_def),
}
```

**LLM name map** (keyed by human-readable `server_name/tool_name` — what the LLM sees):
```
{
  "filesystem/read_file":     "abc123/read_file",
  "filesystem/list_dir":      "abc123/list_dir",
  "github/github_search":     "def456/github_search",
}
```

**Why two maps**: The LLM must receive stable, human-readable tool names so it can reason about them (e.g., `filesystem/read_file`). UUIDs (`abc123`) in tool names would confuse the LLM. The internal registry uses UUIDs for uniqueness — server names can be renamed without invalidating the registry.

**Name collision policy**: If two servers share the same `name` (prevented by the `UNIQUE` DB constraint), this is impossible at rest. If a server is renamed to collide with an existing one, the API returns 400.

The `ChatOrchestrator` receives the merged tool list:
- RAGenie built-in tools (from `src/mcp/tools.py`) — plain names, no `/`
- All enabled external MCP tools (from `MCPClientManager.list_all_tools()`) — `server_name/tool_name` format

When the LLM emits a tool call, the orchestrator checks for `/` to identify external tools, then calls `MCPClientManager.call_tool(llm_tool_name, args)`. The manager resolves `llm_tool_name` (`filesystem/read_file`) → internal `tool_id` (`abc123/read_file`) via the LLM name map.

---

## API Endpoints

```
GET    /api/mcp-servers                        List all servers with status + tool counts
POST   /api/mcp-servers                        Create server config (and optionally connect)

POST   /api/mcp-servers/import                 Import from Claude Desktop JSON format
GET    /api/mcp-servers/export                 Export to Claude Desktop JSON format

GET    /api/mcp-servers/{id}                   Get single server (config + status + tools)
PATCH  /api/mcp-servers/{id}                   Update config (reconnects if connected)
DELETE /api/mcp-servers/{id}                   Delete config + disconnect

POST   /api/mcp-servers/{id}/connect           Connect (or reconnect) server
POST   /api/mcp-servers/{id}/disconnect        Disconnect server
GET    /api/mcp-servers/{id}/tools             List tools discovered from server
POST   /api/mcp-servers/{id}/test              Test connection: connect, list tools, disconnect
```

> **FastAPI route ordering constraint**: Static path segments (`/import`, `/export`) MUST be declared in the router **before** any `/{id}` parameterised routes. In FastAPI, routes are matched in registration order — if `GET /api/mcp-servers/{id}` is registered first, a request to `GET /api/mcp-servers/export` will match `{id}="export"` and return 404. In `mcp_client_routes.py`, always register the `/import` and `/export` route handlers before the `/{id}` handlers.

### Claude Desktop JSON Import/Export Format

Import/export uses the same JSON shape as `claude_desktop_config.json`, so users can copy-paste their Claude Desktop config directly into RAGenie:

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/Users/me/Documents"],
      "env": {}
    },
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": { "GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_..." }
    }
  }
}
```

---

## Frontend Page Layout

```
Settings > MCP Servers
─────────────────────────────────────────────────────────────
[+ Add Server]  [Import JSON]  [Export JSON]

┌─────────────────────────────────────────────────────────┐
│ ● filesystem          stdio   ✅ connected   8 tools  [Edit] [···] │
│ ● github              stdio   ⚠ error        —       [Edit] [···] │
│ ○ my-remote-server    sse     ○ disconnected  —       [Edit] [···] │
└─────────────────────────────────────────────────────────┘

[Selected: filesystem]
──────────────────────────────────
Name:       filesystem
Transport:  stdio
Command:    npx
Args:       -y @modelcontextprotocol/server-filesystem /Users/me
Env vars:   (none)
Enabled:    [✅ toggle]

[Connect]  [Disconnect]  [Refresh Tools]  [Save]  [Delete]

Tools discovered (8):
  📎 read_file        Read the contents of a file at the given path
  📎 write_file       Write content to a file
  📎 list_directory   List contents of a directory
  ...
```

---

## Error Handling & Reconnect Policy

| Scenario | Behaviour |
|---|---|
| subprocess exits unexpectedly | `status → ERROR`, log error, attempt reconnect after 10 s (max 3 retries) |
| SSE connection lost | `status → ERROR`, attempt reconnect with exponential back-off (5 s, 15 s, 45 s) |
| `tools/call` timeout (>30 s) | Return error result to LLM; do not crash connection |
| Server returns `isError: true` | Surface error text to LLM as tool result; do not crash |
| Invalid config (missing command) | Validation error at API layer; never stored |

---

## Startup Migration

On first boot after this module is deployed, `ServerConfigStore.migrate_from_yaml(config)` is called:

1. Read `config.mcp_clients` (the existing `MCPClientServerConfig` list).
2. For each entry not already present in `mcp_servers` table (matched by `name`), insert it.
3. Log how many entries were migrated.
4. The original `config.yaml` `mcp_clients` section is left untouched (read-only for migration, write path is now the DB).

---

## Config Model (`src/config/models.py`)

Add to the `Config` root model:

```python
class MCPClientConfig(BaseModel):
    store_path: str = Field(default="data/mcp_client/servers.db")

class Config(BaseModel):
    ...                                        # existing fields
    mcp_client: MCPClientConfig = Field(default_factory=MCPClientConfig)   # ← new
```

Add to `config/config.yaml`:

```yaml
# MCP Client Configuration
mcp_client:
  store_path: "data/mcp_client/servers.db"   # SQLite DB for MCP server configs
```

---

## API Routes — Accessing `app_state`

The `mcp_client_routes.py` router needs access to the `MCPClientManager` instance created in `startup_event`. Follow the same pattern used by `analytics_routes.py`:

```python
# In mcp_client_routes.py
from .app import app_state

def _get_manager() -> MCPClientManager:
    mgr = app_state.get("mcp_client_manager")
    if mgr is None:
        raise HTTPException(status_code=503, detail="MCP client manager not initialised")
    return mgr
```

Each route handler calls `_get_manager()` at the top, then delegates to `MCPClientManager` methods.

---

## Security Considerations

- **Environment variables with secrets** (API keys) are stored in the `env` column as JSON. The column is never returned in list endpoints (only returned for single-server `GET` and the editor form, where the user has already authenticated).
- **Command injection**: `command` and `args` are passed as a list (not shell-interpolated). The subprocess is never launched with `shell=True`.
- **SSRF for SSE transport**: URL validation rejects `file://`, `ftp://`, and private/loopback ranges when the app is deployed in a multi-user context (configurable).
- **Rate limiting**: `tools/call` through the API inherits the existing `RateLimitMiddleware`.
