#!/usr/bin/env python3
"""Test all MCP tools and print results in a table."""

import asyncio
import json
import sys
import time
import urllib.request
import urllib.parse
import threading
from queue import Queue, Empty

BASE = "http://localhost:8001"


def post_message(session_id: str, payload: dict) -> None:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{BASE}/messages?sessionId={session_id}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5):
        pass


def sse_listener(session_id_holder: list, msg_queue: Queue, stop_event: threading.Event):
    """Opens /sse, extracts sessionId from endpoint event, then forwards message events."""
    req = urllib.request.Request(f"{BASE}/sse", headers={"Accept": "text/event-stream"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        event_type = None
        for raw in resp:
            if stop_event.is_set():
                break
            line = raw.decode().rstrip("\n\r")
            if line.startswith("event:"):
                event_type = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                data = line.split(":", 1)[1].strip()
                if event_type == "endpoint":
                    # data is like /messages?sessionId=abc123
                    sid = urllib.parse.parse_qs(urllib.parse.urlparse(data).query).get("sessionId", [None])[0]
                    session_id_holder.append(sid)
                elif event_type == "message":
                    try:
                        msg_queue.put(json.loads(data))
                    except Exception:
                        pass
            elif line == "":
                event_type = None


def call_tool(session_id: str, msg_queue: Queue, rpc_id: int, tool_name: str, args: dict) -> dict:
    payload = {
        "jsonrpc": "2.0",
        "id": rpc_id,
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": args},
    }
    post_message(session_id, payload)
    deadline = time.time() + 60
    while time.time() < deadline:
        try:
            msg = msg_queue.get(timeout=1)
            if msg.get("id") == rpc_id:
                return msg
        except Empty:
            continue
    return {"error": "timeout"}


def main():
    session_id_holder = []
    msg_queue = Queue()
    stop_event = threading.Event()

    # Start SSE listener thread
    t = threading.Thread(target=sse_listener, args=(session_id_holder, msg_queue, stop_event), daemon=True)
    t.start()

    # Wait for sessionId
    deadline = time.time() + 10
    while not session_id_holder and time.time() < deadline:
        time.sleep(0.1)

    if not session_id_holder:
        print("ERROR: Could not connect to MCP server at http://localhost:8001/sse")
        print("Make sure RAGenie server is running: python run_server.py")
        sys.exit(1)

    session_id = session_id_holder[0]
    print(f"Connected — session: {session_id}\n")

    # Send initialize
    post_message(session_id, {
        "jsonrpc": "2.0", "id": 0, "method": "initialize",
        "params": {"protocolVersion": "2024-11-05", "clientInfo": {"name": "test", "version": "1.0"}, "capabilities": {}}
    })
    # Drain initialize response
    try:
        msg_queue.get(timeout=3)
    except Empty:
        pass

    # Define tests
    tests = [
        ("list_documents",   {}),
        ("search_documents", {"query": "machine learning", "top_k": 2}),
        ("search_web",       {"query": "what is ollama LLM", "max_results": 3}),
        ("execute_task",     {"request": "Remind me to test MCP at 5pm"}),
        ("ask_ragenie",      {"question": "What documents are indexed?"}),
    ]

    results = []
    for i, (tool, args) in enumerate(tests, start=1):
        print(f"Testing {tool}...", flush=True)
        t0 = time.time()
        resp = call_tool(session_id, msg_queue, i, tool, args)
        elapsed = round(time.time() - t0, 1)

        if "error" in resp and "result" not in resp:
            status = "TIMEOUT"
            output = str(resp.get("error", ""))
        elif resp.get("result", {}).get("isError"):
            status = "ERROR"
            content = resp.get("result", {}).get("content", [])
            output = content[0].get("text", "")[:120] if content else ""
        else:
            status = "OK"
            content = resp.get("result", {}).get("content", [])
            output = content[0].get("text", "")[:120] if content else ""

        results.append((tool, status, elapsed, output))

    stop_event.set()

    # Print table
    print()
    print(f"{'Tool':<22} {'Status':<8} {'Time(s)':<9} {'Result (truncated)'}")
    print("─" * 100)
    for tool, status, elapsed, output in results:
        out_clean = output.replace("\n", " ")
        print(f"{tool:<22} {status:<8} {elapsed:<9} {out_clean[:65]}")

    print()
    ok = sum(1 for _, s, _, _ in results if s == "OK")
    print(f"Passed: {ok}/{len(results)}")


if __name__ == "__main__":
    main()
