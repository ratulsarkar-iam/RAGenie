#!/usr/bin/env python3
"""
RAGenie MCP stdio server — for use with Claude Desktop and other stdio-based MCP clients.

Add to Claude Desktop's config (~/.claude/claude_desktop_config.json):
{
  "mcpServers": {
    "ragenie": {
      "command": "python",
      "args": ["/path/to/RAGenie/mcp_stdio.py"],
      "env": {}
    }
  }
}
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.config.loader import load_config
from src.rag.page_index_store import PageIndexStore
from src.search.search_service import SearchService
from src.mcp.tools import set_dependencies, call_tool, TOOLS


PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "ragenie", "version": "1.0.0"}


def _send(obj: dict) -> None:
    line = json.dumps(obj)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def _error(rpc_id, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": rpc_id, "error": {"code": code, "message": message}}


async def handle(body: dict) -> None:
    rpc_id = body.get("id")
    method = body.get("method", "")
    params = body.get("params") or {}

    if method == "initialize":
        _send({
            "jsonrpc": "2.0", "id": rpc_id,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "serverInfo": SERVER_INFO,
                "capabilities": {"tools": {}},
            },
        })

    elif method == "initialized":
        pass  # notification, no response

    elif method == "ping":
        _send({"jsonrpc": "2.0", "id": rpc_id, "result": {}})

    elif method == "tools/list":
        _send({"jsonrpc": "2.0", "id": rpc_id, "result": {"tools": TOOLS}})

    elif method == "tools/call":
        name = params.get("name", "")
        args = params.get("arguments") or {}
        try:
            text = await call_tool(name, args)
            _send({
                "jsonrpc": "2.0", "id": rpc_id,
                "result": {"content": [{"type": "text", "text": text}], "isError": False},
            })
        except Exception as e:
            _send({
                "jsonrpc": "2.0", "id": rpc_id,
                "result": {"content": [{"type": "text", "text": str(e)}], "isError": True},
            })

    elif method == "resources/list":
        _send({"jsonrpc": "2.0", "id": rpc_id, "result": {"resources": []}})

    else:
        _send(_error(rpc_id, -32601, f"Method not found: {method}"))


async def main() -> None:
    config = load_config()

    rag_store = PageIndexStore(config.rag.index_path)
    rag_store.load()

    search_service = SearchService(config.search)

    set_dependencies(rag_store=rag_store, search_service=search_service)

    loop = asyncio.get_event_loop()

    def read_stdin():
        return sys.stdin.readline()

    while True:
        line = await loop.run_in_executor(None, read_stdin)
        if not line:
            break
        line = line.strip()
        if not line:
            continue
        try:
            body = json.loads(line)
            await handle(body)
        except json.JSONDecodeError:
            _send(_error(None, -32700, "Parse error"))


if __name__ == "__main__":
    asyncio.run(main())
