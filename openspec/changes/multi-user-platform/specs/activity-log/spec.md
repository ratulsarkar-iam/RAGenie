# Spec: activity-log

## Purpose

Record what each user does in the app — chat messages, searches, keyword and MCP server management, document uploads, tool calls, logins — in a queryable, per-user-attributed SQLite log, distinct from the existing security-only `AuditLogger`.

## Module

New package `src/activity/`:

| Module | Responsibility |
|---|---|
| `__init__.py` | Package exports |
| `models.py` | `ActivityEventType` (enum), `ActivityEvent`, `ActivityEventCreate` |
| `activity_store.py` | SQLite CRUD |
| `activity_logger.py` | Fire-and-forget façade with redaction |

New route module `src/api/activity_routes.py`.

## Database

Path: `data/activity/activity.db` (configurable via `config.activity.store_path`).

```sql
CREATE TABLE IF NOT EXISTS activity_log (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL,
    event_type  TEXT NOT NULL,
    description TEXT NOT NULL,
    metadata    TEXT,              -- JSON string, nullable
    created_at  TEXT NOT NULL      -- ISO-8601 UTC
);
CREATE INDEX IF NOT EXISTS idx_activity_user_created ON activity_log(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_activity_event_type ON activity_log(event_type);
```

## Public Interface

```python
class ActivityEventType(str, Enum):
    LOGIN = "login"
    LOGOUT = "logout"
    CHAT_MESSAGE = "chat_message"
    DOCUMENT_UPLOADED = "document_uploaded"
    KEYWORD_CREATED = "keyword_created"
    KEYWORD_UPDATED = "keyword_updated"
    KEYWORD_DELETED = "keyword_deleted"
    NEWS_SEARCH = "news_search"
    MCP_SERVER_CREATED = "mcp_server_created"
    MCP_SERVER_CONNECTED = "mcp_server_connected"
    MCP_TOOL_CALL = "mcp_tool_call"
    MEMORY_SEARCH = "memory_search"

class ActivityStore:
    def __init__(self, db_path: str): ...
    def log(self, user_id: str, event_type: str, description: str, metadata: Optional[dict] = None) -> ActivityEvent: ...
    def list_for_user(self, user_id: str, event_type: Optional[str] = None, page: int = 1, limit: int = 50) -> List[ActivityEvent]: ...
    def list_all(self, user_id: Optional[str] = None, event_type: Optional[str] = None, page: int = 1, limit: int = 50) -> List[ActivityEvent]: ...
    def count_for_user(self, user_id: str) -> int: ...

class ActivityLogger:
    def __init__(self, store: ActivityStore): ...
    def log(self, user_id: str, event_type: str, description: str, metadata: Optional[dict] = None) -> None:
        """Fire-and-forget; catches and logs (via core logger) any internal exception, never raises."""
```

## API

```
GET /api/activity                 (auth)       → list_for_user(current_user.id, event_type?, page, limit)
GET /api/activity/admin           (admin)      → list_all(user_id?, event_type?, page, limit)
```

## Behavior

- `ActivityLogger.log(...)` is called at each instrumented call site (see `tasks.md` Phase 4.2) immediately after the primary action succeeds. Failures in logging must never propagate to the caller — wrapped in try/except, warnings logged via `src/core/logging_config.get_logger`.
- `description` and `metadata` values pass through `src/security/sensitive_data_redactor.redact_dict`/equivalent before persistence, to avoid storing raw secrets (e.g. API keys pasted into a chat message).
- Pagination follows the existing `page`/`limit` convention used in `src/api/news_routes.py` (`GET /api/news`).

## Validation Rules

- `event_type` must be one of `ActivityEventType`'s values; unknown types are still stored (forward-compatible) but the API's `event_type` filter only recognizes known enum values for filtering purposes.
- `/api/activity/admin` requires `role == "admin"` (`require_admin` dependency); returns `403` otherwise.

## Error Behavior

- Store-level exceptions during `log()` are caught internally — the calling request must always succeed even if activity logging fails.
- Malformed `event_type` filter on the read APIs returns an empty list, not an error.

## Tests (`tests/test_activity_store.py`, `tests/test_activity_api.py`)

- `log()` then `list_for_user()` round-trip returns the event with correct fields.
- Pagination returns correct page slices, `count_for_user` matches total.
- `GET /api/activity` only returns the requester's own events, never another user's.
- `GET /api/activity/admin` as a non-admin → `403`; as admin, returns events for any requested `user_id`.
- Redaction: logging a description containing an obvious API-key-shaped string results in a redacted value in the stored row.
