# Keyword Management Specification

## Overview

The Keyword Manager is the entry point for the news feature. It provides full CRUD control over the set of tracked search terms and exposes scheduling parameters (fetch interval, article cap) per keyword. Changes to keywords are reflected in the background scheduler in real time.

## Requirements

### Functional Requirements
- Create a keyword with a term, optional fetch interval, and optional article cap.
- List all keywords with their current status (`enabled`/`disabled`) and `last_fetched_at` timestamp.
- Enable or disable a keyword without deleting it.
- Update a keyword's fetch interval or article cap.
- Delete a keyword and cascade-delete all associated articles and summaries.
- Trigger an immediate ("fetch now") run for a specific keyword outside the scheduled interval.
- Enforce uniqueness on `term` (case-insensitive).

### Non-Functional Requirements
- All operations complete in < 50 ms (SQLite, no network).
- Keyword count is expected to be small (< 100); no pagination required.
- Scheduler job registration/removal must be synchronised with keyword mutations.

## Data Model

```python
class KeywordCreate(BaseModel):
    term: str = Field(..., min_length=1, max_length=200)
    fetch_interval_minutes: int = Field(default=60, ge=5, le=1440)
    max_articles_per_fetch: int = Field(default=10, ge=1, le=100)

class Keyword(BaseModel):
    id: str                              # UUID4
    term: str
    enabled: bool
    fetch_interval_minutes: int
    max_articles_per_fetch: int
    created_at: datetime
    last_fetched_at: Optional[datetime]
    article_count: int                   # Computed on read
    last_error: Optional[str]            # Last fetch error message, if any
```

## KeywordStore Interface

```python
class KeywordStore:
    def __init__(self, db_path: str): ...

    def create(self, req: KeywordCreate) -> Keyword: ...
    def list_all(self) -> List[Keyword]: ...
    def get(self, keyword_id: str) -> Optional[Keyword]: ...
    def update(self, keyword_id: str, **fields) -> Keyword: ...
    def delete(self, keyword_id: str) -> bool: ...
    def get_due(self) -> List[Keyword]:
        """Return all enabled keywords whose next fetch time has passed."""
    def mark_fetched(self, keyword_id: str, error: Optional[str] = None) -> None:
        """Update last_fetched_at and optionally set last_error."""
```

## API Endpoints

### `GET /api/keywords`
Returns all keywords ordered by `created_at` DESC.

**Response `200`**
```json
[
  {
    "id": "uuid",
    "term": "Narendra Modi",
    "enabled": true,
    "fetch_interval_minutes": 60,
    "max_articles_per_fetch": 10,
    "created_at": "2025-05-11T10:00:00Z",
    "last_fetched_at": "2025-05-11T11:00:00Z",
    "article_count": 47,
    "last_error": null
  }
]
```

### `POST /api/keywords`
Create a new keyword.

**Request body**: `KeywordCreate`
**Response `201`**: `Keyword`
**Error `409`**: Term already exists.
**Error `422`**: Validation failure.

### `PATCH /api/keywords/{id}`
Partial update. Accepts any subset of `{enabled, fetch_interval_minutes, max_articles_per_fetch}`.

**Response `200`**: Updated `Keyword`
**Error `404`**: Keyword not found.

### `DELETE /api/keywords/{id}`
Delete keyword and all associated articles and summaries (CASCADE).

**Response `200`**: `{"status": "deleted", "id": "..."}`
**Error `404`**: Keyword not found.

### `POST /api/keywords/{id}/fetch-now`
Enqueue an immediate fetch for the keyword, bypassing the normal schedule.

**Response `202`**: `{"status": "fetch_enqueued", "keyword_id": "..."}`
**Error `404`**: Keyword not found.
**Error `503`**: News service not initialised.

## Scheduler Integration

```python
# On create/enable:
scheduler.register_keyword(keyword)

# On update (interval changed):
scheduler.remove_keyword(keyword_id)
scheduler.register_keyword(updated_keyword)

# On disable or delete:
scheduler.remove_keyword(keyword_id)
```

The scheduler uses APScheduler's `IntervalTrigger` with `minutes=keyword.fetch_interval_minutes`. Job IDs are `f"news_fetch_{keyword_id}"`.

## Validation Rules

| Field | Rule |
|---|---|
| `term` | 1–200 chars; trimmed; stored lowercase for uniqueness check |
| `fetch_interval_minutes` | 5–1440 (5 min to 24 h) |
| `max_articles_per_fetch` | 1–100 |

## Testing Strategy

### Unit Tests (`tests/test_news_keyword_store.py`)
- Create keyword succeeds.
- Duplicate term returns error.
- `list_all` returns all keywords.
- `get_due` only returns enabled keywords past their interval.
- Delete cascades to articles.
- `mark_fetched` updates timestamp and error field.

### Integration Tests (`tests/test_news_api.py`)
- `POST /api/keywords` → `201` with correct payload.
- Duplicate `POST` → `409`.
- `DELETE` then `GET` → `404`.
- `PATCH enabled=false` stops future fetches.
