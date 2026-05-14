# News Aggregator & Summarizer — Design Document

## Architecture Overview

```
┌───────────────────────────────────────────────────────────────┐
│                     RAGenie Frontend (React)                  │
│                                                               │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │  News Page                                               │ │
│  │  ┌────────────────┐   ┌───────────────────────────────┐  │ │
│  │  │  Keyword Panel │   │  Article Feed                 │  │ │
│  │  │  (Add/Pause/   │   │  (title, source, date,        │  │ │
│  │  │   Delete)      │   │   summary, read-more link)    │  │ │
│  │  └────────────────┘   └───────────────────────────────┘  │ │
│  └──────────────────────────────────────────────────────────┘ │
└──────────────────────────┬────────────────────────────────────┘
                           │  REST (axios)
                           ▼
┌───────────────────────────────────────────────────────────────┐
│                     FastAPI Backend                           │
│                                                               │
│  ┌────────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  /api/keywords │  │ /api/news    │  │  /api/news/      │  │
│  │  CRUD router   │  │ articles     │  │  summarize/{id}  │  │
│  └───────┬────────┘  └──────┬───────┘  └────────┬─────────┘  │
│          │                  │                   │             │
│  ┌───────▼──────────────────▼───────────────────▼──────────┐  │
│  │                   NewsService                            │  │
│  │  ┌───────────────┐   ┌──────────────┐  ┌─────────────┐  │  │
│  │  │  KeywordStore │   │  ArticleStore│  │  Summariser │  │  │
│  │  │  (SQLite)     │   │  (SQLite)    │  │  (Ollama)   │  │  │
│  │  └───────────────┘   └──────────────┘  └─────────────┘  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                               │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  NewsScheduler (APScheduler)                             │  │
│  │  • Per-keyword fetch jobs (IntervalTrigger)              │  │
│  │  • Retention cleanup job every 6 h (fixed interval)      │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                               │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  NewsFetcher   →  ArticleProcessor  →  RAG Ingestion     │  │
│  │  (NewsAPI)         (filter/dedup)       (PageIndexStore) │  │
│  └──────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────┘
```

## Module Breakdown

### `src/news/` — New Package

| Module | Responsibility |
|---|---|
| `models.py` | Pydantic models: `Keyword`, `Article`, `Summary` |
| `keyword_store.py` | SQLite CRUD for keywords |
| `article_store.py` | SQLite CRUD for articles + summaries |
| `fetcher.py` | NewsAPI client, pagination, error handling |
| `processor.py` | Deduplication, relevance filtering, RAG ingestion |
| `summariser.py` | Ollama LLM prompt + batch summarisation |
| `scheduler.py` | APScheduler-backed per-keyword fetch jobs |
| `news_service.py` | Facade: orchestrates fetch → process → summarise |

### `src/api/news_routes.py`
REST router mounted at `/api/keywords` and `/api/news`.

## Data Models

```python
class Keyword(BaseModel):
    id: str                    # UUID
    term: str                  # e.g. "Narendra Modi"
    enabled: bool = True
    fetch_interval_minutes: int = 60
    max_articles_per_fetch: int = 10
    created_at: datetime
    last_fetched_at: Optional[datetime]

class Article(BaseModel):
    id: str                    # SHA-256 of URL (dedup key)
    keyword_id: str
    title: str
    content: str               # Full article body
    url: str
    source: str
    published_at: Optional[datetime]
    fetched_at: datetime
    is_summarised: bool = False
    rag_doc_id: Optional[str]  # Set when ingested into RAG

class ArticleSummary(BaseModel):
    article_id: str
    summary: str               # LLM-generated abstractive summary
    model: str                 # Ollama model name used
    generated_at: datetime
```

## Database Schema

```sql
-- keywords table
CREATE TABLE keywords (
    id              TEXT PRIMARY KEY,
    term            TEXT NOT NULL UNIQUE,
    enabled         INTEGER NOT NULL DEFAULT 1,
    fetch_interval_minutes INTEGER NOT NULL DEFAULT 60,
    max_articles_per_fetch INTEGER NOT NULL DEFAULT 10,
    created_at      TEXT NOT NULL,
    last_fetched_at TEXT
);

-- articles table
CREATE TABLE articles (
    id              TEXT PRIMARY KEY,   -- SHA-256(url)
    keyword_id      TEXT NOT NULL,
    title           TEXT NOT NULL,
    content         TEXT NOT NULL,
    url             TEXT NOT NULL UNIQUE,
    source          TEXT,
    published_at    TEXT,
    fetched_at      TEXT NOT NULL,
    is_summarised   INTEGER NOT NULL DEFAULT 0,
    rag_doc_id      TEXT,
    FOREIGN KEY (keyword_id) REFERENCES keywords(id) ON DELETE CASCADE
);

-- summaries table
CREATE TABLE article_summaries (
    article_id      TEXT PRIMARY KEY,
    summary         TEXT NOT NULL,
    model           TEXT NOT NULL,
    generated_at    TEXT NOT NULL,
    FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE
);
```

## Data Flow

```
User adds keyword "Narendra Modi"
        │
        ▼
KeywordStore.create(term="Narendra Modi")
        │
        ▼
Scheduler registers a job: every 60 min → NewsService.run_for_keyword(id)
        │
        ▼
NewsFetcher.fetch(keyword="Narendra Modi", page_size=10)
   → GET https://newsapi.org/v2/everything?q=...
   → Returns List[RawArticle]
        │
        ▼
ArticleProcessor.process(articles, keyword_id)
   → Deduplicate by SHA-256(url)
   → Filter: title/content must contain keyword tokens
   → ArticleStore.save(article)
   → PageIndexStore.ingest(article)    ← optional RAG ingestion
        │
        ▼
Summariser.summarise_pending()
   → SELECT articles WHERE is_summarised=0
   → For each: LLM.generate(SUMMARISE_PROMPT.format(content=...))
   → ArticleStore.save_summary(article_id, summary)
        │
        ▼
[Every 6 h] ArticleStore.delete_older_than(retention_days=3)
   → DELETE articles WHERE fetched_at < now() - 3 days
   → Collect rag_doc_ids → PageIndexStore.delete_document(id)  (if ingest_into_rag)
        │
        ▼
Frontend polls GET /api/news?keyword_id=...
   → Returns articles + summaries as unified JSON
```

## API Endpoints

### Keywords
```
GET    /api/keywords                        List all keywords
POST   /api/keywords                        Create keyword
PATCH  /api/keywords/{id}                   Update (enable/disable, interval)
DELETE /api/keywords/{id}                   Delete keyword + cascade articles
POST   /api/keywords/{id}/fetch-now         Trigger immediate fetch
```

### Articles
```
GET    /api/news?keyword_id=&page=&limit=   Paginated article+summary list
GET    /api/news/{article_id}               Single article detail
POST   /api/news/{article_id}/summarize     Re-generate summary on demand
DELETE /api/news/{article_id}               Remove article
```

## LLM Summarisation Prompt

```
You are a concise news summariser.

Read the article below and produce a 3-5 sentence abstractive summary.
Focus on: who, what, when, where, and why.
Do NOT add your own commentary or opinions.

=== ARTICLE ===
{content}
=== END ARTICLE ===

Summary:
```

## Configuration Extensions

```yaml
# config/config.yaml — new section
news:
  enabled: false
  db_path: "data/news/news.db"
  newsapi_key: ""              # Set via NEWSAPI_KEY env var
  default_fetch_interval_minutes: 60
  default_max_articles_per_fetch: 10
  summarise_on_fetch: true     # Auto-summarise after each fetch
  ingest_into_rag: false       # Ingest articles into RAG index for chat
  max_content_chars: 8000      # Truncate article body before summarising
  summary_max_sentences: 5
  retention_days: 3            # Hard cap: delete articles older than this
  cleanup_interval_hours: 6    # How often the periodic retention job runs
```

## Frontend Page Structure

```
/news                          ← new route in App.tsx
├── KeywordPanel (left sidebar or top bar)
│   ├── KeywordForm (add new)
│   └── KeywordList
│       └── KeywordCard (term, status, last-fetched, actions)
└── ArticleFeed (main area)
    ├── FilterBar (select keyword, date range, summarised only)
    └── ArticleList
        └── ArticleCard
            ├── Title + Source + Published date
            ├── Summary (collapsible LLM output)
            └── "Read full article" external link
```

## Integration with Existing Systems

| Existing system | Integration point |
|---|---|
| `LangChainLLM` | `Summariser` calls `llm_wrapper.generate(prompt)` directly |
| `PageIndexStore` | `ArticleProcessor` calls `ingest()` when `ingest_into_rag=true` |
| `ProactiveEngine` | Can trigger `NewsService.run_all()` as a proactive job |
| `app_state` | `NewsService` stored at `app_state["news_service"]` |
| `startup_event` | Initialise `NewsService`, run startup retention cleanup, start scheduler |
| `shutdown_event` | Stop scheduler gracefully |

## Error Handling Strategy

| Error | Handling |
|---|---|
| NewsAPI rate limit (429) | Exponential back-off; log and skip until next interval |
| Network failure | Catch `requests.RequestException`; mark keyword `last_error` |
| Empty article body | Skip article; log warning |
| LLM summarisation failure | Retry once; store `summary="[Summary unavailable]"` |
| Missing API key | Disable news module at startup; warn in logs |
| Retention cleanup DB error | Log error; continue — non-fatal |
| RAG purge failure (expired article) | Log warning; article already deleted from news DB — non-fatal |

## Dependencies to Add

```
newsapi-python>=0.2.7      # Official NewsAPI Python client
apscheduler>=3.10.0        # Per-keyword scheduling
```

Both are lightweight and have no conflicting requirements with the existing stack.
