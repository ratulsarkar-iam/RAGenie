# Multi-User Platform — Design Document

## Architecture Overview

```
┌───────────────────────────────────────────────────────────────────────┐
│                       RAGenie Frontend (React)                        │
│                                                                        │
│  ┌────────────────┐   ┌───────────────────┐   ┌────────────────────┐  │
│  │  Login/Register │   │  AuthContext      │   │  Activity Page     │  │
│  │  Page (new)     │──▶│  (new — token,    │──▶│  (new — self +     │  │
│  │                 │   │   user, axios     │   │   admin views)     │  │
│  │                 │   │   interceptor)    │   │                    │  │
│  └────────────────┘   └─────────┬─────────┘   └──────────┬─────────┘  │
│                                  │  Authorization: Bearer <jwt>        │
│  Existing pages (Chat, News, MCPServersPage, ...) — unchanged UI,      │
│  now all requests carry the auth header via the shared axios client   │
└──────────────────────────────────┬────────────────────────────────────┘
                                    │ REST / WS
                                    ▼
┌───────────────────────────────────────────────────────────────────────┐
│                          FastAPI Backend                               │
│                                                                        │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │  require_auth (mandatory) — resolves User from Bearer JWT        │ │
│  │  Applied to: /chat, /api/keywords*, /api/mcp-servers*,            │ │
│  │              /api/news*, /upload, /api/memory*, /api/activity*   │ │
│  └───────────────────────────┬──────────────────────────────────────┘ │
│                               │ current_user.id                        │
│         ┌─────────────────────┼─────────────────────┬────────────────┐│
│         ▼                     ▼                     ▼                ││
│  ┌─────────────┐     ┌───────────────────┐   ┌─────────────────────┐ ││
│  │ KeywordStore │     │ MCPClientManager  │   │  ActivityLogger      │ ││
│  │ (scoped by  │     │  Registry (scoped  │   │  (new — writes to   │ ││
│  │  user_id)   │     │   by user_id)      │   │   activity.db)      │ ││
│  └─────────────┘     └───────────────────┘   └─────────────────────┘ ││
│                                                                        │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │  UserStore (existing) — users table, PBKDF2 hashing              │ │
│  └──────────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────┘
```

## 1. Auth Enforcement

### JWT payload
No schema change needed — `create_access_token({"sub": user_id, "role": role})` already embeds `user_id` as `sub` (`src/api/auth_routes.py:73`). We rely on this everywhere instead of introducing a new field.

### Dependency change
Replace `require_auth_when_enabled` with `require_auth` (already exists, raises 401 unconditionally) on all data-owning routes:
- `src/api/app.py`: `/chat`, `/history/*`, `/documents*`, `/upload`, `/chat-upload`, `/api/memory/*`, `/api/tasks/execute`, `/api/feedback*`, `/api/learning/*`, `/api/proactive/*`
- `src/api/news_routes.py`: all `/api/keywords*` and `/api/news*` routes (currently have **no** auth dependency at all)
- `src/api/mcp_client_routes.py`: all `/api/mcp-servers*` routes (currently have **no** auth dependency at all)

`config.auth.enabled` becomes effectively always-on for these routes; the config flag is kept for local/dev convenience (e.g. running without login during isolated backend testing) but the default flips to `true`.

### WebSocket auth
`src/api/websocket.py` (`handle_chat_websocket`) currently accepts no auth. Add token extraction from the WS query string (`?token=<jwt>`) or the first message frame, resolve `current_user`, and reject the connection (close code 4401) if invalid. Attach `current_user.id` to conversation lookups.

### Conversation ownership
`ChatOrchestrator` conversation history is currently keyed only by `conversation_id` (client-supplied, no ownership check — any authenticated user could read another's `conversation_id` if guessed). Add a `conversations` ownership map (`conversation_id → user_id`) in-memory or persisted; `/history/{conversation_id}` and `/chat` verify the requester owns the conversation (create-on-first-use registers ownership).

### Migration of existing data
On first startup after this change, a **one-time migration script** (run in `startup_event`, idempotent — checks a `migrations` marker table or a `user_id IS NULL` sentinel):
1. Ensure at least one user exists (bootstrap admin via `UserStore.count_users() == 0` → prompt or use `ADMIN_BOOTSTRAP_EMAIL`/`ADMIN_BOOTSTRAP_PASSWORD` env vars if set, else defer until first `/register` call, which — per existing logic — auto-grants admin to the first registrant).
2. `UPDATE keywords SET user_id = <admin_id> WHERE user_id IS NULL`
3. `UPDATE mcp_servers SET user_id = <admin_id> WHERE user_id IS NULL`
4. Log a summary of how many rows were migrated.

If no admin exists yet (fresh install), migration is skipped and re-attempted on next startup after the first `/register` call creates the admin — implemented as a lazy check inside the relevant store methods (`get_or_migrate_owner()`), not a hard startup blocker.

## 2. Keyword Isolation

### Schema change (`src/news/keyword_store.py`)
```sql
CREATE TABLE IF NOT EXISTS keywords (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,               -- NEW
    term            TEXT NOT NULL,
    term_lower      TEXT NOT NULL,
    enabled         INTEGER NOT NULL DEFAULT 1,
    fetch_interval_minutes INTEGER NOT NULL DEFAULT 60,
    max_articles_per_fetch INTEGER NOT NULL DEFAULT 10,
    created_at      TEXT NOT NULL,
    last_fetched_at TEXT,
    last_error      TEXT,
    UNIQUE(user_id, term_lower)                  -- CHANGED from UNIQUE(term_lower)
);
CREATE INDEX IF NOT EXISTS idx_keywords_user ON keywords(user_id);
```
Migration path for existing DBs (`ALTER TABLE keywords ADD COLUMN user_id TEXT` guarded by try/except like the existing `headers` column pattern in `server_store.py:64-68`, then backfill via the migration step above, then the app-level uniqueness check moves from a global `term_exists(term)` to `term_exists(user_id, term)` — SQLite `ALTER TABLE` cannot add a `UNIQUE` constraint after creation, so uniqueness enforcement moves to the **application layer** in `KeywordStore.create()`/`update()`, mirroring the existing check in `news_routes.py:63-65`).

### API changes (`src/api/news_routes.py`)
Every route gains `current_user: User = Depends(require_auth)` and passes `current_user.id` into the corresponding `NewsService`/`KeywordStore` call:
```
GET    /api/keywords                    → list_keywords(user_id)
POST   /api/keywords                    → create_keyword(user_id, body)   [409 if user already has this term]
PATCH  /api/keywords/{id}               → update_keyword(user_id, id, body)  [404 if not owned]
DELETE /api/keywords/{id}               → delete_keyword(user_id, id)        [404 if not owned]
POST   /api/keywords/{id}/fetch-now     → fetch_now(user_id, id)             [404 if not owned]
GET    /api/news                        → list_articles(user_id, keyword_id?, ...)
```
Ownership check pattern: `KeywordStore.get(id)` returns the row; the route/service verifies `row.user_id == current_user.id` before allowing mutation, else `404` (not `403`, to avoid leaking existence of other users' keyword IDs).

### Scheduler
`NewsScheduler` (`src/news/scheduler.py`) currently runs fetch jobs per keyword_id globally — this is fine unchanged, since fetch jobs are keyed by `keyword_id` (already unique per row) regardless of owner. No change needed there; only `KeywordStore`/`NewsService`/routes need scoping.

### Articles
`ArticleStore` is keyed by `keyword_id` (`article_store.py`), which is already effectively user-scoped transitively (each keyword belongs to one user). `GET /api/news` filters by `keyword_id` optionally — when `keyword_id` is omitted, the route must first fetch `list_keywords(user_id)` and constrain the article query to that user's keyword IDs, to avoid leaking all users' articles.

## 3. MCP Server Isolation

### Schema change (`src/mcp_client/server_store.py`)
```sql
CREATE TABLE IF NOT EXISTS mcp_servers (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL,                   -- NEW
    name        TEXT NOT NULL,
    transport   TEXT NOT NULL CHECK(transport IN ('stdio', 'sse', 'http')),
    enabled     INTEGER NOT NULL DEFAULT 1,
    command     TEXT,
    args        TEXT,
    env         TEXT,
    url         TEXT,
    headers     TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    UNIQUE(user_id, name)                         -- CHANGED from UNIQUE(name)
);
CREATE INDEX IF NOT EXISTS idx_mcp_servers_user ON mcp_servers(user_id);
```
Same `ALTER TABLE ... ADD COLUMN` + app-layer uniqueness approach as keywords (`get_by_name` becomes `get_by_name(user_id, name)`).

### `MCPClientManager` scoping (the hard part)
Today `MCPClientManager` is a single global instance owning global `_connections`, `_registry`, `_llm_name_map` dicts (`src/mcp_client/manager.py:27-29`), instantiated once in `app.py` startup and shared by the singleton `ChatOrchestrator`.

**Chosen approach: per-user manager instances, lazily created, cached in a dict.**
```python
# New: src/mcp_client/multi_user_manager.py (or extend manager.py)
class MultiUserMCPManagerRegistry:
    def __init__(self, store_factory: Callable[[str], ServerConfigStore]):
        self._managers: Dict[str, MCPClientManager] = {}   # user_id -> manager
        self._store_factory = store_factory

    async def get_or_create(self, user_id: str) -> MCPClientManager:
        if user_id not in self._managers:
            store = self._store_factory(user_id)   # ServerConfigStore filtered by user_id
            mgr = MCPClientManager(store)
            await mgr.initialize_all()
            self._managers[user_id] = mgr
        return self._managers[user_id]

    async def shutdown_all(self) -> None:
        await asyncio.gather(*(m.shutdown() for m in self._managers.values()), return_exceptions=True)
```
- `ServerConfigStore` gains a `user_id` filter parameter on every method (`list(user_id)`, `get(id, user_id)`, `create(user_id, data)`, etc.) — same DB file, filtered queries, no per-user DB files (keeps ops simple).
- `ChatOrchestrator.achat()` / tool-building step resolves the caller's `MCPClientManager` via `MultiUserMCPManagerRegistry.get_or_create(user_id)` instead of a single injected instance. This requires passing `user_id` through the chat call chain (`achat(message, conversation_id, user_id=...)`).
- Idle managers (no activity for N minutes) can be evicted/disconnected to bound memory/subprocess usage — deferred to Phase 8 (polish), not required for correctness in v1.
- REST routes in `mcp_client_routes.py` resolve the manager the same way: `mgr = await registry.get_or_create(current_user.id)`.

### API changes (`src/api/mcp_client_routes.py`)
Every route gains `current_user: User = Depends(require_auth)`; internally resolves the per-user manager/store as above. Route paths and shapes are unchanged — only the resolution of "which manager" changes.

## 4. Activity Log

### New package: `src/activity/`

| Module | Responsibility |
|---|---|
| `__init__.py` | Package exports |
| `models.py` | `ActivityEvent`, `ActivityEventType` (enum), `ActivityEventCreate` |
| `activity_store.py` | SQLite CRUD: `log()`, `list_for_user()`, `list_all()` (admin), `count_for_user()` |
| `activity_logger.py` | Thin façade used by call-sites: `ActivityLogger.log(user_id, event_type, description, metadata)` — wraps `activity_store` with try/except so a logging failure never breaks the primary request |

### Schema
```sql
CREATE TABLE IF NOT EXISTS activity_log (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL,
    event_type  TEXT NOT NULL,     -- e.g. "chat_message", "keyword_created", "mcp_tool_call", "login"
    description TEXT NOT NULL,     -- short human-readable summary
    metadata    TEXT,              -- JSON blob, event-specific detail
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_activity_user_created ON activity_log(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_activity_event_type ON activity_log(event_type);
```
Path: `data/activity/activity.db` (configurable via new `config.activity.store_path`, mirroring `mcp_client.store_path` pattern).

### Event taxonomy (v1)
| event_type | Emitted from |
|---|---|
| `login` / `logout` | `auth_routes.py` (`/login`), frontend calls a `/api/auth/logout` no-op endpoint or purely client-side (see below) |
| `chat_message` | `websocket.py` / `app.py` `/chat` — on each user message sent |
| `document_uploaded` | `/upload`, `/chat-upload` |
| `keyword_created` / `keyword_updated` / `keyword_deleted` | `news_routes.py` |
| `news_search` (article list query) | `news_routes.py` `GET /api/news` |
| `mcp_server_created` / `mcp_server_connected` / `mcp_tool_call` | `mcp_client_routes.py`, `MCPClientManager.call_tool` |
| `memory_search` | `/api/memory/search` |

### Injection pattern
`ActivityLogger` instance created at startup (`app_state["activity_logger"]`), injected wherever needed via the same `app_state` accessor pattern already used by `news_routes.py:_svc()`. Each instrumented call site is a single extra line: `activity_logger.log(current_user.id, "keyword_created", f"Created keyword '{term}'", {"keyword_id": kw.id})` — fire-and-forget, never raises.

### REST API (`src/api/activity_routes.py`, new)
```
GET /api/activity                 → self activity, paginated, optional event_type filter, current_user only
GET /api/activity/admin           → admin-only, optional user_id filter, all users (403 if not admin)
```

## 5. Frontend Auth UI

### `AuthContext` (new `frontend/src/contexts/AuthContext.tsx`)
- State: `user`, `accessToken`, `refreshToken`, `isAuthenticated`, `isLoading`.
- Persists tokens in `localStorage` (`ragenie_access_token`, `ragenie_refresh_token`).
- `login(email, password)`, `register(email, password)`, `logout()`, `refreshAccessToken()`.
- Wraps the app in `main.tsx`, alongside existing `ThemeContext`/`ToastContext`/`TranslationContext`.

### Axios interceptor
Existing `frontend/src/api/*.ts` clients need a shared axios instance with a request interceptor that attaches `Authorization: Bearer <accessToken>` and a response interceptor that, on `401`, attempts a silent refresh via `/api/auth/refresh` once before redirecting to `/login`.

### Login/Register Page (new `frontend/src/components/auth/LoginPage.tsx`)
- Matches existing visual language: `GenieLogo`, Tailwind utility classes, dark/light via `ThemeContext`, toast feedback via `ToastContext` on error.
- Tabbed or toggled Login / Register form.
- On success, `AuthContext` stores tokens and `App.tsx` renders the main app.

### Route gating (`App.tsx`)
- If `!isAuthenticated`, render `LoginPage` only.
- Add a "Logout" action + current user email display near the existing `Sidebar` header/profile area.
- `logout()` clears tokens and fires a `logout` activity event (best-effort, fire-and-forget before clearing token) then returns to `LoginPage`.

## 6. Frontend Activity UI

### `ActivityPage.tsx` (new, `frontend/src/components/ActivityPage.tsx`)
- Self view: chronological feed, grouped by day, icon per `event_type`, filter dropdown (event type), search box (description contains).
- Admin view (role === "admin"): additional user-picker dropdown to inspect any user's activity; reuses the same list component with a different data source (`/api/activity/admin?user_id=`).
- Pagination: infinite scroll or "Load more", consistent with `SearchHistoryPanel.tsx`'s existing pagination pattern.
- New API client `frontend/src/api/activityApi.ts`: `listMyActivity(params)`, `listAllActivity(params)` (admin).
- New nav item in `Sidebar.tsx`: "Activity" (visible to all authenticated users; admin sees an "All Users" toggle within the page, not a separate nav item).

## Config Model Additions (`src/config/models.py`)

```python
class ActivityConfig(BaseModel):
    enabled: bool = True
    store_path: str = Field(default="data/activity/activity.db")

class Config(BaseModel):
    ...
    activity: ActivityConfig = Field(default_factory=ActivityConfig)   # new
```
`config/config.yaml` gains:
```yaml
activity:
  enabled: true
  store_path: "data/activity/activity.db"
```
`AuthConfig.enabled` default changes from `false` to `true` (or documented as the recommended production setting — final call left to implementation time based on how disruptive this is to existing local dev workflows).

## Security Considerations

- **404 vs 403 on cross-user resource access**: always return 404 (not 403) when a user references another user's `keyword_id`/`server_id`, to avoid confirming existence.
- **Activity log contains user-generated text** (chat messages, search terms) — reuse `src/security/sensitive_data_redactor.py` (already used by `AuditLogger`) to redact obvious secrets before persisting `description`/`metadata`.
- **Admin activity view** is gated by `require_admin` (existing dependency, `src/auth/dependencies.py:71-75`).
- **WebSocket auth token** should not be logged in plaintext server logs — pass via query string but ensure the WS handshake log line redacts the token.

## Rollout / Migration Risk

- Existing local installs running with `auth.enabled=false` and existing keywords/MCP servers with no owner will hit the lazy migration path on first admin registration. Document this clearly in `README.md` and add a startup log line stating how many legacy rows were migrated and to which admin account.
- Because SQLite can't add `UNIQUE` constraints via `ALTER TABLE`, uniqueness for `(user_id, term_lower)` and `(user_id, name)` is enforced at the application layer only — acceptable for this app's SQLite-based scale, but must be tested for race conditions (two concurrent creates with the same term) via a `try/except sqlite3.IntegrityError`-free path (app-layer check-then-insert is not atomic; acceptable risk for v1, documented as a known limitation).
