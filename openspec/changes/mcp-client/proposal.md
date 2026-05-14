# MCP Client Module for RAGenie

## Overview

This proposal adds a full **MCP Client** capability to RAGenie, allowing it to connect to any external MCP server (local or remote) — just like Claude Desktop does — with all server configurations managed live from the Web UI. No config-file edits or restarts required.

## Problem Statement

RAGenie currently acts only as an **MCP server** (exposing its own tools to other clients). It has no ability to consume tools from external MCP servers. The existing `MCPManager` in `src/tasks/mcp_manager.py` is a thin stub: it handles only stdio transport, does not implement the MCP JSON-RPC handshake, and is hard-wired to `config.yaml` at startup. Key gaps:

- No live CRUD for MCP server configs — every change requires editing `config.yaml` and restarting the process.
- No SSE/HTTP transport support — cannot connect to remote or network-based MCP servers.
- No tool discovery — tools from external servers are never surfaced to the LLM or chat.
- No connection status visibility — users cannot tell if a server is connected or broken.
- No UI for server management — there is no Web UI surface for this at all.

## Proposed Solution

Implement four tightly integrated subsystems:

1. **Server Config Store** — SQLite-backed persistence for MCP server configurations. Survives restarts, allows live CRUD, and migrates existing `config.yaml` `mcp_clients` entries on first boot.

2. **MCP Client Engine** — A production-grade async MCP client supporting both `stdio` (subprocess) and `sse` (HTTP Server-Sent Events) transports, implementing the full MCP JSON-RPC 2.0 handshake: `initialize`, `tools/list`, `tools/call`, with per-server connection lifecycle and automatic reconnect.

3. **Config API** — REST endpoints (`/api/mcp-servers/*`) for CRUD, connect/disconnect, status polling, and per-server tool listing. Changes take effect immediately at runtime.

4. **Settings UI** — A dedicated **MCP Servers** settings page in the React frontend, matching the UX familiarity of Claude Desktop's config panel: form-based entry, live connection status, discovered-tool browser, and a JSON import/export compatible with Claude Desktop's `claude_desktop_config.json` format.

## Non-Goals

- RAGenie acting as an MCP proxy (forwarding other clients to external servers).
- OAuth / token-refresh flows for remote MCP servers (API key in env vars is sufficient for v1).
- `resources/*` and `prompts/*` MCP capabilities (tools only for v1).
- Multi-user scoping of MCP server configs (single-user app).

## Benefits

- **Zero-restart config changes** — add, modify, or remove an MCP server at any time from the UI.
- **Unified tool surface** — the LLM sees RAGenie's built-in tools and all external MCP tools in a single list.
- **Transport parity with Claude Desktop** — supports the same `stdio` and `sse` transports Claude Desktop uses.
- **Familiar UX** — users already know how to configure MCP servers in Claude Desktop; RAGenie mirrors that model.
- **Fully local** — no cloud dependency; works with local MCP servers (e.g., filesystem, calendar) and remote ones.

## Implementation Strategy

Five specs cover the full scope:

| Spec | What it covers |
|---|---|
| `server-store` | SQLite CRUD for server configs, startup migration from `config.yaml` |
| `client-engine` | Async MCP client: stdio + SSE transports, JSON-RPC handshake, reconnect |
| `tool-integration` | Tool registry, orchestrator integration, LLM tool-call routing |
| `config-api` | REST API: CRUD, connect/disconnect, status, tool listing, JSON import/export |
| `settings-ui` | React settings page: form editor, status indicators, tool browser, JSON editor |
