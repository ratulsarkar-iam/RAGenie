# Multi-User Platform — Implementation Tasks

## Phase 1: Auth Enforcement Foundation

### 1.1 Config
- [ ] Add `activity: ActivityConfig` to `src/config/models.py` (`enabled: bool = True`, `store_path: str`)
- [ ] Add `activity:` block to `config/config.yaml`
- [ ] Decide + document default for `auth.enabled` (recommend flipping default to `true`)

### 1.2 Mandatory auth on existing routes
- [ ] `src/api/app.py`: replace `require_auth_when_enabled` with `require_auth` on `/chat`, `/history/*`, `/documents*`, `/upload`, `/chat-upload`, `/api/memory/*`, `/api/tasks/execute`, `/api/feedback*`, `/api/learning/*`, `/api/proactive/*`
- [ ] `src/api/news_routes.py`: add `current_user: User = Depends(require_auth)` to every route
- [ ] `src/api/mcp_client_routes.py`: add `current_user: User = Depends(require_auth)` to every route
- [ ] `src/api/websocket.py`: extract + validate JWT from WS query string/first frame; close with 4401 on failure; attach `current_user` to session state

### 1.3 Conversation ownership
- [ ] Add ownership tracking (`conversation_id → user_id`) in `ChatOrchestrator` or a small new store
- [ ] `/chat` and `/history/{conversation_id}` verify ownership (404 if not owned by requester)

### 1.4 Data migration
- [ ] Implement lazy migration helper: on first admin registration (or startup if admin already exists), backfill `user_id` for legacy keyword/mcp_server rows created before this change
- [ ] Add startup log line reporting migration counts
- [ ] Write test: fresh DB with legacy (no `user_id`) rows → migration assigns them to first admin

---

## Phase 2: Keyword Isolation

### 2.1 Schema
- [ ] `src/news/keyword_store.py`: add `user_id TEXT NOT NULL` column via guarded `ALTER TABLE` (same pattern as `headers` in `server_store.py`)
- [ ] Change all `CREATE TABLE` DDL for fresh installs to include `UNIQUE(user_id, term_lower)` (drop the old `UNIQUE` on `term_lower` alone)
- [ ] Add `idx_keywords_user` index

### 2.2 Store methods
- [ ] `KeywordStore.create(user_id, req)`, `list_all(user_id)`, `get(id)` (unchanged signature, ownership checked by caller), `update(id, patch)`, `delete(id)`, `term_exists(user_id, term)`, `get_due()` (unchanged — cross-user, scheduler-internal)
- [ ] Update `NewsService` methods to accept/pass `user_id` through to the store

### 2.3 Routes
- [ ] `src/api/news_routes.py`: thread `current_user.id` through `list_keywords`, `create_keyword`, `update_keyword` (404 if not owned), `delete_keyword` (404 if not owned), `fetch_now` (404 if not owned)
- [ ] `GET /api/news`: when `keyword_id` omitted, constrain to `current_user`'s own keyword IDs
- [ ] Write tests: `tests/test_keyword_isolation.py` — user A creates "IPL", user B creates "BPL", both create "NASA" independently; user A cannot PATCH/DELETE user B's keyword (404)

---

## Phase 3: MCP Server Isolation

### 3.1 Schema
- [ ] `src/mcp_client/server_store.py`: add `user_id TEXT NOT NULL` column via guarded `ALTER TABLE`
- [ ] Fresh-install DDL: `UNIQUE(user_id, name)` instead of `UNIQUE(name)`
- [ ] Add `idx_mcp_servers_user` index
- [ ] Update `ServerConfigStore` methods to accept `user_id`: `create(user_id, data)`, `get(id)` + ownership check by caller, `get_by_name(user_id, name)`, `list(user_id)`, `update`, `delete`

### 3.2 Per-user manager registry
- [ ] Implement `MultiUserMCPManagerRegistry` (new file, e.g. `src/mcp_client/multi_user_manager.py`)
- [ ] Wire into `src/api/app.py` startup: replace singleton `mcp_client_manager` in `app_state` with the registry
- [ ] Update `ChatOrchestrator` to accept `user_id` in its chat entrypoint and resolve the per-user manager via the registry instead of a fixed instance
- [ ] Update `src/mcp_client/manager.py`'s tools-changed callback wiring to be per-user-manager-instance (each manager instance registers its own callback into the orchestrator's rebuild path, scoped by user)
- [ ] Update shutdown_event to call `registry.shutdown_all()`

### 3.3 Routes
- [ ] `src/api/mcp_client_routes.py`: add `current_user` dependency; resolve manager via `await registry.get_or_create(current_user.id)`
- [ ] Ownership checks on `/api/mcp-servers/{id}` PATCH/DELETE/connect/disconnect/tools/test (404 if not owned)
- [ ] Write tests: `tests/test_mcp_server_isolation.py` — user A's tools never appear in user B's `list_all_tools()`; user A cannot connect/disconnect user B's server

---

## Phase 4: Activity Log Module

### 4.1 Package scaffold
- [ ] Create `src/activity/__init__.py`
- [ ] `src/activity/models.py`: `ActivityEventType` enum, `ActivityEvent`, `ActivityEventCreate`
- [ ] `src/activity/activity_store.py`: SQLite CRUD (`log`, `list_for_user`, `list_all`, `count_for_user`), schema per `design.md`
- [ ] `src/activity/activity_logger.py`: fire-and-forget façade wrapping `activity_store`, with redaction via `src/security/sensitive_data_redactor.py`
- [ ] Write unit tests: `tests/test_activity_store.py`

### 4.2 Instrumentation
- [ ] `src/api/auth_routes.py`: log `login` on successful `/login`
- [ ] `src/api/app.py`: log `chat_message` in `/chat` and the WS chat path; log `document_uploaded` in `/upload`, `/chat-upload`
- [ ] `src/api/news_routes.py`: log `keyword_created`/`keyword_updated`/`keyword_deleted`, `news_search` on `GET /api/news`
- [ ] `src/api/mcp_client_routes.py`: log `mcp_server_created`, `mcp_server_connected`
- [ ] `src/mcp_client/manager.py` (or per-call site in orchestrator): log `mcp_tool_call` with tool name (redact args if they look sensitive)
- [ ] `src/api/app.py` `/api/memory/search`: log `memory_search`

### 4.3 REST API
- [ ] `src/api/activity_routes.py` (new): `GET /api/activity` (self, paginated, `event_type` filter), `GET /api/activity/admin` (admin-only, `user_id` filter)
- [ ] Register `activity_router` in `app.py`
- [ ] Instantiate `ActivityLogger`, put in `app_state["activity_logger"]` during startup
- [ ] Write API tests: `tests/test_activity_api.py`

---

## Phase 5: Frontend — Auth UI

### 5.1 Auth context & API client
- [ ] `frontend/src/contexts/AuthContext.tsx`: token/user state, `login`, `register`, `logout`, `refreshAccessToken`, localStorage persistence
- [ ] `frontend/src/api/authApi.ts`: `login()`, `register()`, `getMe()`, `refresh()`, `changePassword()`
- [ ] Add shared axios instance (or update existing per-file clients) with request interceptor (attach Bearer token) and response interceptor (401 → silent refresh once → else force logout)
- [ ] Wrap `AuthProvider` around the app in `frontend/src/main.tsx`

### 5.2 Login/Register page
- [ ] `frontend/src/components/auth/LoginPage.tsx`: toggled login/register form, `GenieLogo`, Tailwind styling matching existing theme, error toasts via `ToastContext`
- [ ] `App.tsx`: if `!isAuthenticated`, render only `LoginPage`; else render existing app shell
- [ ] Add user email + "Logout" control near `Sidebar` header

---

## Phase 6: Frontend — Activity UI

### 6.1 API client
- [ ] `frontend/src/api/activityApi.ts`: `listMyActivity(params)`, `listAllActivity(params)` (admin)

### 6.2 Activity page
- [ ] `frontend/src/components/ActivityPage.tsx`: chronological feed grouped by day, event-type icon/badge, filter dropdown, search box, pagination ("Load more")
- [ ] Admin-only user picker (visible when `user.role === "admin"`) to inspect any user's feed
- [ ] Add "Activity" nav item to `Sidebar.tsx`
- [ ] Wire route/section into `App.tsx`

---

## Phase 7: Polish & Verification

- [ ] End-to-end manual test: register user A, create keyword "IPL" + MCP server "srv1"; register user B, create keyword "BPL" + "NASA"; confirm A can also create "NASA" without conflict; confirm neither sees the other's keywords/servers/activity
- [ ] Verify WebSocket chat requires a valid token and conversation ownership is enforced
- [ ] Confirm activity log captures all Phase 4.2 instrumented events end-to-end for both users
- [ ] Update `README.md`: multi-user setup section (registration flow, admin bootstrap, activity log overview)
- [ ] Confirm no plaintext secrets/tokens appear in `logs/server.log` or `activity_log` table (spot-check via `sensitive_data_redactor`)
