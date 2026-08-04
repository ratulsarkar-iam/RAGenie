# Security Hardening — Tasks

> All items implemented. See design.md for details on each change.

## Phase 1 — Critical (implement first)

- [x] **P1-BUG-1** Fix double user-message insertion in WebSocket agent path
  - `src/api/websocket.py`: remove unconditional `add_message("user")` pre-add
  - Add `add_message("user")` at top of `stream_simple_response()` and reasoning block

- [x] **P1-BUG-2** Fix `seed_news_server` runtime errors
  - `src/api/mcp_client_routes.py` line 669: `connect_server(config)` not `connect_server(config.id)`
  - `src/api/mcp_client_routes.py` lines 648, 676: replace non-existent `get_tools_for_server()`

- [x] **P1-BUG-3** Cancel proactive background task on graceful shutdown
  - `src/api/app.py` `shutdown_event`: add task cancellation with `contextlib.suppress`

- [x] **P1-SEC-1** Add `require_auth_when_enabled` conditional auth dependency
  - `src/auth/dependencies.py`: add `_auth_enabled`, `set_auth_enabled()`, `require_auth_when_enabled`
  - `src/api/app.py`: call `set_auth_enabled(config.auth.enabled)` in startup
  - `src/api/app.py`: add `Depends(require_auth_when_enabled)` to all business endpoints
  - `src/api/mcp_client_routes.py`: add dependency at router level
  - `src/api/websocket.py`: validate `token` query param in `handle_chat_websocket`

- [x] **P1-SEC-2** Replace raw `str(e)` in HTTP 500 responses with generic messages
  - `src/api/app.py`: all affected routes
  - `src/api/mcp_client_routes.py`: MCP agent chat endpoint

- [x] **P1-SEC-3** Add input size limits to request models
  - `src/api/app.py`: `MemoryStoreRequest`, `FeedbackRequest`, `CorrectionRequest`, `TaskRequest`
  - `src/mcp_client/models.py`: `MCPChatRequest.message`

## Phase 2 — Medium

- [x] **P2-INFRA-1** Atomic RAG index write
  - `src/rag/page_index_store.py`: write to `.tmp`, then `os.replace()`

- [x] **P2-INFRA-2** Config-driven rate limits
  - `src/security/rate_limit_middleware.py`: accept `RateLimitConfig` param
  - `src/api/app.py`: pass `config.security.rate_limiting` to middleware (requires lifespan approach — use startup override instead)

## Phase 3 — Low

- [x] **P3-DEP-1** Fix `datetime.utcnow()` deprecation
  - `src/auth/user_store.py` lines 69, 99

- [x] **P3-QUA-1** Move `import re` to module top
  - `src/api/app.py`

- [x] **P3-PERF-1** Remove artificial 10ms streaming delay
  - `src/api/websocket.py`: remove `await asyncio.sleep(0.01)` from all token loops

- [x] **P3-SEC-1** CSP — replace `unsafe-eval` with `wasm-unsafe-eval`
  - `src/security/security_headers_middleware.py`

- [x] **P3-SEC-2** Tighten CORS allowed methods and headers
  - `src/api/app.py`
