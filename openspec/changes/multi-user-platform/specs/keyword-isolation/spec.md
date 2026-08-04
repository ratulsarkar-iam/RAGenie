# Spec: keyword-isolation

## Purpose

Scope all news-keyword data by `user_id` so each user manages an independent keyword set. Two different users may create the same term (e.g. both create "NASA") without conflict, while a single user cannot create the same term twice.

## Module

`src/news/keyword_store.py`, `src/news/news_service.py`, `src/api/news_routes.py`

## Database

```sql
CREATE TABLE IF NOT EXISTS keywords (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,
    term            TEXT NOT NULL,
    term_lower      TEXT NOT NULL,
    enabled         INTEGER NOT NULL DEFAULT 1,
    fetch_interval_minutes INTEGER NOT NULL DEFAULT 60,
    max_articles_per_fetch INTEGER NOT NULL DEFAULT 10,
    created_at      TEXT NOT NULL,
    last_fetched_at TEXT,
    last_error      TEXT,
    UNIQUE(user_id, term_lower)
);
CREATE INDEX IF NOT EXISTS idx_keywords_user ON keywords(user_id);
```

Legacy DBs: `user_id` added via guarded `ALTER TABLE ... ADD COLUMN user_id TEXT` (SQLite cannot retrofit a `UNIQUE` constraint on an existing table — uniqueness for `(user_id, term_lower)` is therefore enforced at the application layer in `KeywordStore.create`/`update`, not the DB schema, for pre-existing databases).

## Public Interface

```python
class KeywordStore:
    def create(self, user_id: str, req: KeywordCreate) -> Keyword: ...
    def list_all(self, user_id: str) -> List[Keyword]: ...
    def get(self, keyword_id: str) -> Optional[Keyword]: ...          # caller checks ownership
    def update(self, keyword_id: str, patch: KeywordUpdate) -> Optional[Keyword]: ...
    def delete(self, keyword_id: str) -> bool: ...
    def term_exists(self, user_id: str, term: str) -> bool: ...
    def get_due(self) -> List[Keyword]: ...                          # unchanged, cross-user (scheduler-internal)
```

## API

```
GET    /api/keywords                    (auth) → list_keywords(current_user.id)
POST   /api/keywords                    (auth) → create_keyword(current_user.id, body); 409 if term_exists(user_id, term)
PATCH  /api/keywords/{id}               (auth) → 404 if keyword.user_id != current_user.id, else update
DELETE /api/keywords/{id}               (auth) → 404 if not owned, else delete
POST   /api/keywords/{id}/fetch-now     (auth) → 404 if not owned, else enqueue fetch
GET    /api/news                        (auth) → if keyword_id given, verify ownership (404 if not owned);
                                                   if omitted, constrain to current_user's own keyword_ids
```

## Validation Rules

- `term_exists` check is scoped to `(user_id, term_lower)` — the same term is allowed across different users, forbidden twice for the same user.
- Ownership check on mutation routes is always `404` on mismatch, never `403`.

## Error Behavior

- `409 Conflict` — creating a term the same user already has.
- `404 Not Found` — mutating/fetching a keyword_id owned by a different user, or that doesn't exist.

## Tests (`tests/test_keyword_isolation.py`)

- User A creates "IPL"; user B creates "BPL" — both succeed, both lists are disjoint.
- Both user A and user B create "NASA" independently — both succeed (no conflict across users).
- User A creates "NASA" twice — second call returns `409`.
- User A attempts `PATCH`/`DELETE` on user B's keyword id — `404`.
- `GET /api/news` without `keyword_id` for user A never returns user B's articles.
