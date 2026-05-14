# Article Processing Specification

## Overview

The Article Processor transforms a list of `RawArticle` objects fetched from the News API into validated, deduplicated, relevance-filtered `Article` records persisted in SQLite. Optionally, processed articles are also ingested into the RAG index so users can ask questions about recent news through the existing chat interface.

## Processing Pipeline

```
List[RawArticle]
       │
       ▼
1. Deduplication    — Drop articles whose SHA-256(url) already exists in DB
       │
       ▼
2. Validation       — Drop articles with empty title or content (< 50 chars)
       │
       ▼
3. Relevance Filter — Drop articles whose title+content do not contain
                      at least one token from the keyword term
       │
       ▼
4. Content Truncation — Truncate content to config.news.max_content_chars
       │
       ▼
5. Persist          — ArticleStore.save(article)
       │
       ▼
6. RAG Ingestion    — (if config.news.ingest_into_rag) PageIndexStore.ingest()
       │
       ▼
Returns List[Article]  (successfully saved articles)
```

## ArticleProcessor Interface

```python
class ArticleProcessor:
    def __init__(
        self,
        article_store: ArticleStore,
        rag_store: Optional[PageIndexStore] = None,
        max_content_chars: int = 8000,
    ): ...

    def process(
        self,
        raw_articles: List[RawArticle],
        keyword: Keyword,
    ) -> ProcessResult:
        """
        Run the full pipeline on raw_articles for the given keyword.

        Returns a ProcessResult summarising counts of accepted/skipped/errors.
        """

@dataclass
class ProcessResult:
    accepted: int       # Saved to DB
    duplicate: int      # Already existed
    irrelevant: int     # Failed relevance filter
    invalid: int        # Missing title/content
    rag_ingested: int   # Ingested into RAG index
    errors: int         # Unexpected failures
```

## Deduplication

```python
import hashlib

def _article_id(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()
```

The `articles.id` column is `SHA-256(url)`. A SQL `INSERT OR IGNORE` handles concurrency safely:

```sql
INSERT OR IGNORE INTO articles (id, keyword_id, title, content, ...)
VALUES (?, ?, ?, ?, ...);
```

## Relevance Filter

```python
def _is_relevant(raw: RawArticle, keyword_term: str) -> bool:
    """
    Returns True if at least one non-trivial keyword token appears
    (case-insensitive) in the article's title or content.
    """
    tokens = [t.lower() for t in keyword_term.split() if len(t) > 2]
    haystack = (raw.title + " " + raw.content).lower()
    return any(token in haystack for token in tokens)
```

Example: keyword `"Narendra Modi"` → tokens `["narendra", "modi"]`. An article mentioning "Modi" in the body passes. An article about "swimming pools" fails.

## ArticleStore Interface

```python
class ArticleStore:
    def __init__(self, db_path: str): ...

    def save(self, article: Article) -> bool:
        """Insert article. Returns True if new, False if duplicate."""

    def get(self, article_id: str) -> Optional[Article]: ...

    def list_by_keyword(
        self,
        keyword_id: str,
        page: int = 1,
        limit: int = 20,
        summarised_only: bool = False,
    ) -> List[ArticleWithSummary]: ...

    def list_pending_summarisation(self, limit: int = 50) -> List[Article]:
        """Return articles where is_summarised=0."""

    def save_summary(self, article_id: str, summary: str, model: str) -> None:
        """Insert/update summary and mark article is_summarised=1."""

    def delete(self, article_id: str) -> bool: ...

    def count_by_keyword(self, keyword_id: str) -> int: ...

    def delete_older_than(self, days: int) -> CleanupResult:
        """
        Delete all articles where fetched_at < now() - `days` days.
        Also removes associated summaries (CASCADE) and returns the
        list of rag_doc_ids that need to be purged from the RAG index.
        """

@dataclass
class CleanupResult:
    deleted: int          # Articles removed from DB
    rag_purged: int       # rag_doc_ids handed back for RAG removal
    errors: int
```

## Retention Policy

### Rule
Articles are kept for a maximum of **`config.news.retention_days`** days (default: **3**) from the time they were fetched (`fetched_at` column). After that they are deleted automatically.

`fetched_at` is used — not `published_at` — because `published_at` can be `NULL` for some sources and may pre-date the fetch by days or weeks.

### Trigger Points

| When | What happens |
|---|---|
| **Server startup** | `ArticleStore.delete_older_than(config.news.retention_days)` is called once synchronously before the scheduler starts. Clears any articles that aged out while the server was offline. |
| **Periodic job** | The `NewsScheduler` registers a fixed-interval job (`id="news_retention_cleanup"`) that runs every **6 hours** and calls the same method. |

### Cleanup Logic

```python
def delete_older_than(self, days: int) -> CleanupResult:
    cutoff = datetime.utcnow() - timedelta(days=days)
    cutoff_iso = cutoff.isoformat()

    with sqlite3.connect(self.db_path) as conn:
        # Collect rag_doc_ids BEFORE deleting (for RAG index purge)
        rows = conn.execute(
            "SELECT rag_doc_id FROM articles "
            "WHERE fetched_at < ? AND rag_doc_id IS NOT NULL",
            (cutoff_iso,)
        ).fetchall()
        rag_ids = [r[0] for r in rows]

        cursor = conn.execute(
            "DELETE FROM articles WHERE fetched_at < ?",
            (cutoff_iso,)
        )
        deleted = cursor.rowcount

    return CleanupResult(deleted=deleted, rag_purged=len(rag_ids), errors=0,
                         rag_doc_ids=rag_ids)
```

`article_summaries` rows are removed automatically via `ON DELETE CASCADE`.

### RAG Index Purge

When `CleanupResult.rag_doc_ids` is non-empty, `NewsService` calls:

```python
for doc_id in result.rag_doc_ids:
    try:
        rag_store.delete_document(doc_id)
    except Exception as e:
        logger.warning(f"Failed to purge RAG doc {doc_id}: {e}")
```

A failure to purge from RAG is non-fatal — the article is already deleted from the news DB.

### Startup Wiring (in `app.py`)

```python
# Inside startup_event(), after NewsService is initialised:
if config.news.enabled:
    cleanup = news_service.run_startup_cleanup()
    logger.info(
        f"News retention cleanup: removed {cleanup.deleted} expired articles "
        f"({cleanup.rag_purged} purged from RAG index)"
    )
```

## RAG Ingestion (Optional)

When `config.news.ingest_into_rag=true`:

```python
doc_text = f"# {article.title}\n\nSource: {article.source}\nDate: {article.published_at}\n\n{article.content}"
doc_id = rag_store.ingest_text(
    text=doc_text,
    metadata={"source": article.url, "type": "news", "keyword_id": article.keyword_id},
)
article_store.update(article.id, rag_doc_id=doc_id)
```

The `rag_doc_id` is stored on the article so it can be removed from the RAG index if the article is deleted.

## Error Handling

| Error | Handling |
|---|---|
| DB write failure | Log error; increment `ProcessResult.errors`; continue |
| RAG ingestion failure | Log warning; article still saved to DB without `rag_doc_id` |
| Content truncation | Non-fatal; logged at DEBUG level |

## Configuration

```yaml
news:
  max_content_chars: 8000    # Characters to keep before summarisation
  ingest_into_rag: false     # Set true to enable RAG ingestion
  retention_days: 3          # Delete articles older than this (based on fetched_at)
  cleanup_interval_hours: 6  # How often the periodic retention job runs
```

## Testing Strategy

### Unit Tests (`tests/test_news_processor.py`)
- Duplicate URL returns `ProcessResult.duplicate=1`, not saved twice.
- Article with no keyword tokens in title/content is filtered (`irrelevant=1`).
- Article with empty content (`< 50 chars`) is dropped (`invalid=1`).
- Content longer than `max_content_chars` is truncated before save.
- RAG ingestion called when `ingest_into_rag=True` and skipped when `False`.
- RAG ingestion failure does not prevent DB save.
- All `ProcessResult` counters correct for mixed input batch.

### Unit Tests — Retention (`tests/test_news_retention.py`)
- `delete_older_than(3)` removes articles with `fetched_at` > 3 days old.
- `delete_older_than(3)` does NOT remove articles with `fetched_at` ≤ 3 days old.
- Associated `article_summaries` rows are removed (CASCADE verified).
- `CleanupResult.deleted` count matches the number of expired rows.
- `CleanupResult.rag_doc_ids` contains only IDs of articles that had `rag_doc_id` set.
- Articles with `rag_doc_id=NULL` do not appear in `rag_doc_ids`.
- Calling `delete_older_than` on an empty DB returns `deleted=0` without error.
- Startup cleanup is called once on `NewsService` init and logs correctly.
- Periodic job is registered on the scheduler with `id="news_retention_cleanup"`.
