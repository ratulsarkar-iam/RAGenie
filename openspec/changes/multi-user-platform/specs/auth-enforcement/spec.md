# Spec: auth-enforcement

## Purpose

Make authentication mandatory across all data-owning REST and WebSocket endpoints, propagate `user_id` from the JWT into every downstream call, enforce conversation ownership, and migrate pre-existing (unowned) data to the first admin account.

## Modules

- `src/auth/dependencies.py` (existing — `require_auth`, `require_admin` reused as-is)
- `src/api/app.py` (modified — swap dependency on protected routes)
- `src/api/news_routes.py` (modified — add auth dependency, currently has none)
- `src/api/mcp_client_routes.py` (modified — add auth dependency, currently has none)
- `src/api/websocket.py` (modified — WS token validation)
- `src/chat/orchestrator.py` (modified — conversation ownership)

## Behavior

### REST
- Every route under `/chat`, `/history`, `/documents`, `/upload`, `/chat-upload`, `/api/memory`, `/api/tasks`, `/api/feedback`, `/api/learning`, `/api/proactive`, `/api/keywords`, `/api/news`, `/api/mcp-servers` requires `Depends(require_auth)`.
- Missing/invalid/expired Bearer token → `401` with `WWW-Authenticate: Bearer` header (existing `require_auth` behavior, unchanged).

### WebSocket
- Client connects with `?token=<jwt>` query parameter (or sends it as the first JSON frame `{"type": "auth", "token": "..."}` if query params are undesirable for the transport).
- Server validates via `decode_token` (existing `src/auth/jwt_manager.py`); on failure, closes the socket with code `4401` and reason `"unauthorized"`.
- On success, `current_user` is attached to the connection's session state and used for all subsequent activity logging and conversation ownership checks for that connection's lifetime.

### Conversation ownership
- First message on a new `conversation_id` registers `conversation_id → user_id`.
- Subsequent requests (chat continuation, `/history/{conversation_id}`, `DELETE /history/{conversation_id}`) verify `owner == current_user.id`; mismatch → `404` (not `403`).

### Data migration
- Triggered lazily: checked once per process lifetime, on the first successful `/api/auth/register` call that creates the very first user (admin), OR on startup if an admin already exists and unowned rows are detected.
- Backfills `keywords.user_id` and `mcp_servers.user_id` for any row where `user_id IS NULL` (or column didn't exist prior to migration) to the admin's `user_id`.
- Idempotent: rows already having a `user_id` are untouched; running migration twice is a no-op.

## Validation Rules

- JWT `sub` claim must resolve to an existing, active (`is_active=1`) user, else treated as unauthenticated.
- WS token validation follows the same rules as REST (`decode_token`, `type != "refresh"`, active user lookup).

## Error Behavior

- `401` on missing/invalid REST auth.
- WS close code `4401` on missing/invalid WS auth.
- `404` (never `403`) when a resource exists but is not owned by the requester — prevents existence leakage.

## Tests

- `tests/test_auth_enforcement.py`:
  - All previously-unauthenticated routes now reject requests without a Bearer token (`401`).
  - Valid token for user A cannot read/modify a conversation owned by user B (`404`).
  - WS connection without token is closed with `4401`; with valid token, proceeds normally.
  - Migration: seed a DB with legacy unowned keyword/mcp_server rows, register the first user, assert rows are backfilled to that user's id.
