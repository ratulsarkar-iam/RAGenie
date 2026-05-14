"""MCP server — exposes RAGenie tools over the Model Context Protocol.

Two transports are served from the same port:
  • SSE            GET  /sse      (legacy, for older MCP clients)
                   POST /messages (legacy session messages)
  • Streamable-HTTP GET/POST /mcp (modern — Claude Desktop ≥ 2025, ChatGPT, etc.)
"""

import asyncio
import json
import uuid
from typing import Dict, Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from starlette.responses import Response

from .tools import get_tools, call_tool
from ..core.logging_config import get_logger

logger = get_logger(__name__)

# ── Session store ──────────────────────────────────────────────────────────────
# Maps session_id -> asyncio.Queue of JSON-RPC response dicts (SSE transport)
_sessions: Dict[str, asyncio.Queue] = {}

# ── MCP protocol constants ─────────────────────────────────────────────────────
PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "ragenie", "version": "1.0.0"}
SERVER_CAPABILITIES = {"tools": {}}


# ── FastAPI sub-app ────────────────────────────────────────────────────────────

def _build_session_manager():
    """Create the MCP low-level server + StreamableHTTPSessionManager."""
    from mcp.server import Server as MCPServer
    from mcp import types as mcp_types
    from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

    low_level = MCPServer("ragenie")

    @low_level.list_tools()
    async def _list_tools() -> list[mcp_types.Tool]:
        return [
            mcp_types.Tool(
                name=t["name"],
                description=t.get("description", ""),
                inputSchema=t.get("inputSchema", {"type": "object", "properties": {}}),
            )
            for t in get_tools()
        ]

    @low_level.call_tool()
    async def _call_tool(name: str, arguments: dict) -> list[mcp_types.TextContent]:
        try:
            text = await call_tool(name, arguments or {})
        except Exception as e:
            text = f"Error: {e}"
        return [mcp_types.TextContent(type="text", text=str(text))]

    return StreamableHTTPSessionManager(
        app=low_level,
        json_response=False,
        stateless=True,
    )


class _MCPApp:
    """Top-level ASGI app: /mcp → StreamableHTTPSessionManager, all else → FastAPI.

    This wrapper intercepts /mcp before FastAPI routing so that the session
    manager can write its own HTTP response directly via the ASGI 'send'
    callable without conflicting with FastAPI's response pipeline.
    """

    def __init__(self, fastapi_app: FastAPI, session_manager):
        self._app = fastapi_app
        self._sm = session_manager

    async def __call__(self, scope, receive, send):
        if (
            scope.get("type") == "http"
            and scope.get("path", "").rstrip("/") == "/mcp"
            and self._sm is not None
        ):
            await self._sm.handle_request(scope, receive, send)
        else:
            await self._app(scope, receive, send)


def create_mcp_app():
    """Return an ASGI app that serves the MCP SSE and streamable-HTTP transports."""
    import contextlib

    try:
        session_manager = _build_session_manager()
    except Exception as e:
        logger.warning(f"Could not build streamable-HTTP session manager: {e}")
        session_manager = None

    @contextlib.asynccontextmanager
    async def _lifespan(app):
        if session_manager is not None:
            async with session_manager.run():
                logger.info("Streamable-HTTP transport active at /mcp")
                yield
        else:
            yield

    fastapi_app = FastAPI(
        title="RAGenie MCP Server",
        docs_url=None,
        redoc_url=None,
        lifespan=_lifespan,
    )

    fastapi_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    @fastapi_app.get("/sse")
    async def sse_connect(request: Request):
        """SSE endpoint — client connects here to establish an MCP session."""
        session_id = uuid.uuid4().hex[:10]
        queue: asyncio.Queue = asyncio.Queue()
        _sessions[session_id] = queue
        logger.info(f"MCP client connected: {session_id}")

        async def event_stream():
            try:
                # Immediately advertise the POST URL for this session
                yield f"event: endpoint\ndata: /messages?sessionId={session_id}\n\n"

                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        msg = await asyncio.wait_for(queue.get(), timeout=25.0)
                        yield f"event: message\ndata: {json.dumps(msg)}\n\n"
                    except asyncio.TimeoutError:
                        yield ": keepalive\n\n"
            finally:
                _sessions.pop(session_id, None)
                logger.info(f"MCP client disconnected: {session_id}")

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @fastapi_app.post("/messages")
    async def handle_message(request: Request, sessionId: str):
        """Receives JSON-RPC 2.0 messages and dispatches to tool handlers."""
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"error": "Invalid JSON"}, status_code=400)

        rpc_id = body.get("id")
        method = body.get("method", "")
        params = body.get("params") or {}

        response: Optional[dict] = None

        if method == "initialize":
            response = {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "result": {
                    "protocolVersion": PROTOCOL_VERSION,
                    "serverInfo": SERVER_INFO,
                    "capabilities": SERVER_CAPABILITIES,
                },
            }

        elif method == "initialized":
            return JSONResponse({"status": "ok"})

        elif method == "ping":
            response = {"jsonrpc": "2.0", "id": rpc_id, "result": {}}

        elif method == "tools/list":
            response = {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "result": {"tools": get_tools()},
            }

        elif method == "tools/call":
            tool_name = params.get("name", "")
            tool_args = params.get("arguments") or {}
            queue = _sessions.get(sessionId)

            async def _run_tool():
                try:
                    text = await call_tool(tool_name, tool_args)
                    msg = {
                        "jsonrpc": "2.0",
                        "id": rpc_id,
                        "result": {
                            "content": [{"type": "text", "text": text}],
                            "isError": False,
                        },
                    }
                except Exception as e:
                    logger.error(f"Tool call '{tool_name}' failed: {e}")
                    msg = {
                        "jsonrpc": "2.0",
                        "id": rpc_id,
                        "result": {
                            "content": [{"type": "text", "text": str(e)}],
                            "isError": True,
                        },
                    }
                if queue:
                    await queue.put(msg)

            asyncio.create_task(_run_tool())
            return JSONResponse({"status": "ok"})

        elif method == "resources/list":
            response = {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "result": {"resources": []},
            }

        else:
            response = {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            }

        queue = _sessions.get(sessionId)
        if queue and response:
            await queue.put(response)

        return JSONResponse({"status": "ok"})

    @fastapi_app.get("/health")
    async def health():
        tools = get_tools()
        return {"status": "ok", "server": SERVER_INFO, "sessions": len(_sessions), "tool_count": len(tools)}

    return _MCPApp(fastapi_app, session_manager)


async def start_mcp_server(host: str = "0.0.0.0", port: int = 8001) -> None:
    """Start the MCP server (SSE + streamable-HTTP) on the given host/port."""
    import uvicorn
    try:
        app = create_mcp_app()
        config = uvicorn.Config(app, host=host, port=port, log_level="info")
        server = uvicorn.Server(config)
        logger.info(f"MCP SSE server starting on http://{host}:{port}/sse")
        await server.serve()
    except Exception as e:
        logger.error(f"MCP SSE server failed to start: {e}")
        raise
