# Security Hardening — Design

## Phase 1 — Critical

### 1.1 Conditional Auth Dependency

Add `_auth_enabled: bool` flag and `set_auth_enabled()` setter to `src/auth/dependencies.py`.  
Create `require_auth_when_enabled` — uses `get_current_user_optional`; raises 401 only when `_auth_enabled=True` and no valid token is present.  
`startup_event` in `app.py` calls `set_auth_enabled(config.auth.enabled)` after the user store is wired.

All business endpoints receive `_: ... = Depends(require_auth_when_enabled)`:
- `/chat` (POST), `/history/{id}` (GET/DELETE), `/documents` (GET), `/documents/{id}` (DELETE/GET summarize)
- `/upload` (POST), `/chat-upload` (POST), `/ws/{client_id}` (WebSocket — via query-param token)
- `/api/memory/*`, `/api/tasks/execute`, `/api/feedback`, `/api/feedback/correction`
- `/api/learning/summary`, `/api/feedback/stats`, `/api/proactive/*`
- `/mcp-servers/*` (entire router — add dependency at `APIRouter` level)

WebSocket auth: accept `token` query param; validate in `handle_chat_websocket` using `decode_token`.

### 1.2 Double User-Message Fix

**Root cause**: `websocket.py` unconditionally calls `orchestrator.conversation.add_message("user", message)` before branching, then `achat()` adds it again internally.

**Fix**:
- Remove the unconditional pre-add at line 131 of `websocket.py`.
- `achat()` already adds the user message → correct for the agent path.
- `stream_simple_response()` does NOT add it internally → add `orchestrator.conversation.add_message("user", message)` at the start of that function.
- Reasoning block in `websocket.py` handles its own `add_message` after the streaming loop (already present at line 254) → add `add_message("user", message)` at the top of the reasoning block.

### 1.3 seed_news_server Bugs

Two bugs on lines 648, 669, 676 of `mcp_client_routes.py`:

| Bug | Broken line | Fix |
|---|---|---|
| `connect_server(config.id)` — passes string, expects `ServerConfig` | 669 | `await mgr.connect_server(config)` |
| `get_tools_for_server(existing.id)` — method does not exist | 648, 676 | `mgr._connections[existing.id].get_tools() if existing.id in mgr._connections else []` |

### 1.4 Proactive Task Cancellation

`shutdown_event` in `app.py` must cancel and await `app_state["proactive_task"]` before returning.

```python
task = app_state.get("proactive_task")
if task and not task.done():
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
```

### 1.5 Generic Error Messages

Replace `raise HTTPException(status_code=500, detail=str(e))` across all routes with a safe sentinel.  
Log the full exception server-side (`logger.error(..., exc_info=True)`); return only a reference message to the client.

```python
logger.error("Chat error", exc_info=True)
raise HTTPException(status_code=500, detail="An internal error occurred. Check server logs.")
```

Affected routes: `/chat`, `/documents/{id}/summarize`, `/upload`, `/chat-upload`, `/api/tasks/execute`, `/mcp-servers/chat`.

### 1.6 Input Size Limits

Add `Field(max_length=...)` constraints to request models:

| Model | Field | Limit |
|---|---|---|
| `MemoryStoreRequest.content` | `str` | 10 000 chars |
| `FeedbackRequest.comment` | `Optional[str]` | 2 000 chars |
| `CorrectionRequest.corrected_response` | `str` | 10 000 chars |
| `MCPChatRequest.message` | `str` | 10 000 chars |
| `TaskRequest.request` | `str` | 4 000 chars |

---

## Phase 2 — Medium

### 2.1 Atomic RAG Index Write

Replace the direct `open(..., 'w')` write in `PageIndexStore.save()` with:
1. Write to `{index_path}.tmp`
2. `os.replace(tmp_path, index_path)` (atomic on POSIX and Windows)

### 2.2 Config-Driven Rate Limits

`RateLimitMiddleware.__init__` accepts `config: Optional[RateLimitConfig] = None`.  
When provided, override `_TIERS`:

```python
if config:
    self._tiers = {
        "upload": (config.upload_rph, 3600),
        "default": (config.default_rpm, 60),
    }
else:
    self._tiers = _TIERS  # fallback defaults
```

`app.py` passes `config.security.rate_limiting` when adding the middleware.

---

## Phase 3 — Low

### 3.1 datetime.utcnow() Deprecation
Replace `datetime.utcnow().isoformat()` with `datetime.now(timezone.utc).isoformat()` in `user_store.py`.

### 3.2 Import Placement
Move `import re` from inside `summarize_document()` to the top of `app.py`.

### 3.3 Streaming Delay
Remove `await asyncio.sleep(0.01)` from token-streaming loops in `websocket.py`. LangChain's async generator back-pressure is sufficient.

### 3.4 CSP — Remove unsafe-eval
Replace `'unsafe-eval'` with `'wasm-unsafe-eval'` in `security_headers_middleware.py`. If the React frontend uses Vite/esbuild with no runtime eval, `'unsafe-eval'` is unnecessary. This is a breaking change only if the app uses `eval()` at runtime (unlikely for a production build).

### 3.5 CORS Tightening
Restrict `allow_methods` to `["GET","POST","PUT","PATCH","DELETE","OPTIONS"]` and `allow_headers` to `["Authorization","Content-Type","Accept"]`.
