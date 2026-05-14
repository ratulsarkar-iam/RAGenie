# News Retrieval Specification

## Overview

The News Retrieval module is responsible for querying an external News API using a keyword, handling pagination, and returning a structured list of raw article dictionaries. It is the only module that makes external network requests; all other modules work with locally-stored data.

## Data Source

**Primary (Recommended): NewsAPI.org**
- Uses the `newsapi-python` client library.
- Endpoint: `GET /v2/everything?q={keyword}&sortBy=publishedAt&language=en&pageSize={n}`
- Free tier: 100 requests/day; up to 100 articles per request.
- Authentication via `NEWSAPI_KEY` environment variable.

**Fallback: Web scraping**
- Use `requests` + `BeautifulSoup` targeting open news RSS feeds if no API key is configured.
- Lower priority; implemented as a separate `RSSFetcher` behind the same interface.

## Fetcher Interface

```python
class NewsFetcher:
    """Fetches raw articles for a keyword from a news source."""

    def fetch(
        self,
        keyword: str,
        page_size: int = 10,
        max_pages: int = 1,
        from_date: Optional[datetime] = None,
    ) -> List[RawArticle]:
        """
        Query the news source and return up to page_size * max_pages articles.

        Parameters:
            keyword    — Search term.
            page_size  — Articles per page (1–100).
            max_pages  — How many result pages to fetch (pagination).
            from_date  — Only return articles published after this date.
                         Defaults to 24 hours ago if None.

        Returns:
            List of RawArticle (see below). Empty list on non-fatal error.
        """
```

## RawArticle Model

```python
class RawArticle(BaseModel):
    title: str
    content: str          # Full article text if available; description fallback
    url: str
    source: str           # e.g. "BBC News"
    published_at: Optional[datetime]
```

> **Note on `content`:** NewsAPI's free tier truncates `content` to 200 characters. The fetcher uses `description` as fallback and logs a warning. The full-text scraping path (`RSSFetcher`) is unaffected.

## Error Handling

| Error condition | Behaviour |
|---|---|
| `NEWSAPI_KEY` not set | Raise `NewsConfigError` at startup; disable news module |
| HTTP 401 (bad key) | Log error; raise `NewsAuthError`; mark keyword `last_error` |
| HTTP 429 (rate limit) | Log warning; apply exponential back-off (1s, 2s, 4s); after 3 retries, skip and return `[]` |
| Network timeout | `requests.Timeout` → retry once (5 s timeout); return `[]` on second failure |
| Empty result set | Return `[]` — not an error |
| Malformed response | Log warning; skip malformed items; return valid articles |

## Pagination Logic

```python
all_articles = []
for page in range(1, max_pages + 1):
    response = client.get_everything(q=keyword, page=page, page_size=page_size, ...)
    articles = response.get("articles", [])
    all_articles.extend(articles)
    if len(articles) < page_size:
        break          # No more pages
    time.sleep(0.2)    # Polite rate limiting between pages
return all_articles
```

## `from_date` Default Strategy

To avoid re-fetching old articles, the fetcher defaults `from_date` to:
```python
from_date = keyword.last_fetched_at or (datetime.utcnow() - timedelta(hours=24))
```

This is passed by `NewsService`, not hardcoded in `NewsFetcher`.

## Configuration

```yaml
news:
  newsapi_key: ""          # Overridden by NEWSAPI_KEY env var
  fetch_timeout_seconds: 10
  fetch_max_retries: 3
  fetch_retry_backoff_base: 1   # seconds; doubled each retry
```

## Testing Strategy

### Unit Tests (`tests/test_news_fetcher.py`)
All tests use `unittest.mock.patch` to mock `newsapi.NewsApiClient.get_everything`.

- Successful fetch returns `List[RawArticle]`.
- Empty API response returns `[]`.
- HTTP 429 triggers retry and eventually returns `[]`.
- Network timeout triggers retry logic.
- Malformed article (missing `url`) is silently skipped.
- `from_date` is passed correctly to API client.
- Pagination: second page fetched when first page is full.
- Pagination stops early when partial page returned.
