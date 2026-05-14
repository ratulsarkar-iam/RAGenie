# Spec: client-engine

## Purpose

Async MCP client engine — transport abstraction plus `MCPClientConnection` — that handles the full MCP JSON-RPC 2.0 protocol lifecycle (initialize, tools/list, tools/call) over both `stdio` and `sse` transports.

## Modules

- `src/mcp_client/transport.py`
- `src/mcp_client/client.py`

---

## Transport Layer (`transport.py`)

### `BaseTransport` (ABC)

```python
class BaseTransport(ABC):
    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def disconnect(self) -> None: ...

    @abstractmethod
    async def send(self, rpc: dict) -> None:
        """Send a JSON-RPC request/notification."""

    @abstractmethod
    async def recv(self) -> dict:
        """
        Block until the next JSON-RPC message arrives from the server.
        For request/response pairs the caller is responsible for matching
        by `id`; the transport just delivers raw frames.
        """

    @property
    @abstractmethod
    def is_connected(self) -> bool: ...
```

---

### `StdioTransport`

```python
class StdioTransport(BaseTransport):
    def __init__(self, command: str, args: List[str], env: Optional[Dict[str, str]])
```

**Behaviour**:
- `connect()`: calls `asyncio.create_subprocess_exec(command, *args, stdin=PIPE, stdout=PIPE, stderr=PIPE, env=merged_env)`
- `send(rpc)`: writes `json.dumps(rpc) + "\n"` to `proc.stdin`
- `recv()`: reads one line from `proc.stdout` using `asyncio` (non-blocking); parses JSON
- `disconnect()`: sends `SIGTERM`; if process does not exit in 5 s, sends `SIGKILL`
- `is_connected`: `proc is not None and proc.returncode is None`

**Stderr**: a background task reads and logs stderr lines at DEBUG level.

---

### `SSETransport`

```python
class SSETransport(BaseTransport):
    def __init__(self, url: str, headers: Optional[Dict[str, str]] = None)
```

**Behaviour**:
- `connect()`:
  1. Open `httpx.AsyncClient` SSE stream to `url` (GET with `Accept: text/event-stream`)
  2. Read first `event: endpoint` frame; extract `sessionId` from the POST URL
  3. Start background task that reads remaining SSE frames and resolves pending futures
- `send(rpc)`: POST `json.dumps(rpc)` to the endpoint URL received in step 2
- `recv()`: pull from an internal `asyncio.Queue` that the background reader populates
- `disconnect()`: cancel background task; close `httpx` client
- `is_connected`: background task is running and HTTP client is open

**Pending-future pattern** (for request/response matching):
- Before `send()`, register a `Future` keyed by `rpc["id"]`
- Background reader resolves futures by matching incoming `"id"` fields
- `call_rpc(method, params, timeout=30)` is the high-level helper that combines send + await future

---

## MCP Client Connection (`client.py`)

```python
class MCPClientConnection:
    def __init__(self, config: ServerConfig)
    
    async def connect(self) -> None:
        """
        1. Build transport from config.transport
        2. transport.connect()
        3. Send 'initialize' RPC
        4. Check protocolVersion: if not "2024-11-05", log a WARNING and continue
           (do NOT raise — forward compatibility; newer servers may return a later date)
        5. Send 'initialized' notification
        6. Send 'tools/list'; cache results as List[ToolDefinition]
        7. Set status = CONNECTED, record last_connected_at
        """

    async def disconnect(self) -> None:
        """
        Graceful teardown.
        status = DISCONNECTED
        """

    async def call_tool(self, name: str, args: dict, timeout: float = 30.0) -> str:
        """
        Send 'tools/call' RPC.
        Returns content[0].text on success.
        Raises MCPToolError if isError=true.
        Raises asyncio.TimeoutError if no response within timeout.
        """

    def get_status(self) -> ServerStatus: ...
    def get_tools(self) -> List[ToolDefinition]: ...
```

### Initialize RPC Payload

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2024-11-05",
    "clientInfo": { "name": "ragenie", "version": "1.0.0" },
    "capabilities": { "tools": {} }
  }
}
```

### Tool ID Construction

When caching tools from `tools/list`, each `ToolDefinition` is populated as:

```python
ToolDefinition(
    server_id   = config.id,           # UUID — internal key
    server_name = config.name,         # human-readable name (e.g. "filesystem")
    tool_id     = f"{config.id}/{tool.name}",   # internal dispatch key
    name        = tool.name,           # bare MCP tool name (e.g. "read_file")
    description = tool.description,
    input_schema= tool.inputSchema,
)
```

`MCPClientManager` derives the LLM-visible name as `f"{config.name}/{tool.name}"` (`filesystem/read_file`) when building `_llm_name_map` — this is NOT stored in `ToolDefinition` itself; it is computed at map-build time.

---

## Reconnect Policy

Implemented in `MCPClientConnection` as a background `asyncio.Task`:

| Attempt | Delay |
|---------|-------|
| 1 | 10 s |
| 2 | 30 s |
| 3 | 60 s |
| > 3 | Give up; status = ERROR; log warning |

Reconnect is triggered when:
- `recv()` raises `EOFError` (subprocess exited)
- `httpx` SSE stream closes unexpectedly
- `connect()` raises an exception during initialization

---

## Custom Exceptions

```python
class MCPConnectionError(Exception): ...     # transport/handshake failure
class MCPToolError(Exception): ...           # tool returned isError=true
class MCPProtocolError(Exception): ...       # unexpected RPC response shape (malformed JSON-RPC)
```

> `MCPProtocolError` is raised for structurally invalid responses (e.g. missing `result` and `error`, non-dict payload). It is **not** raised for an unrecognised `protocolVersion` — that only logs a warning.

---

## Tests (`tests/test_mcp_transport.py`, `tests/test_mcp_client_connection.py`)

### Transport Tests
- `StdioTransport`: mock subprocess; verify send/recv round-trip
- `SSETransport`: mock HTTP server (using `respx`); verify SSE stream reading + POST routing
- Both: disconnect causes `is_connected == False`

### Connection Tests
- Happy path: mock transport that returns valid `initialize` + `tools/list` responses
- `call_tool` happy path: returns content text
- `call_tool` with `isError=true`: raises `MCPToolError`
- `call_tool` timeout: raises `asyncio.TimeoutError`
- Unexpected disconnect triggers reconnect logic
- Unrecognised `protocolVersion` logs a WARNING and continues (does NOT raise)
- Malformed JSON-RPC response (missing both `result` and `error`) raises `MCPProtocolError`
