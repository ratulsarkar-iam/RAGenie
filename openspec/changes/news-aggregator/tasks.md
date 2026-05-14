# News Aggregator & Summarizer — Implementation Tasks

## Phase 1: Foundation (Week 1)

### 1.1 Data Models & Storage
- [x] Create `src/news/` package with `__init__.py`
- [x] Implement `src/news/models.py` — Pydantic models: `Keyword`, `Article`, `ArticleSummary`, `KeywordCreate`, `ArticleListItem`
- [x] Implement `src/news/keyword_store.py` — SQLite CRUD (create, list, get, update, delete, get_due)
- [x] Implement `src/news/article_store.py` — SQLite CRUD (save, get, list_by_keyword, save_summary, get_pending_summarisation, delete, **delete_older_than**)
- [x] Add `news` section to `src/config/models.py` (`NewsConfig`)
- [x] Add `news` block to `config/config.yaml` with defaults (`retention_days: 3`, `cleanup_interval_hours: 6`)

### 1.2 News Retrieval
- [x] Implement `src/news/fetcher.py` — NewsAPI client, `fetch(keyword, page_size)`, pagination, error handling
- [x] Handle missing/invalid API key gracefully (log warning, skip fetch)
- [x] Add exponential back-off for 429 / network errors
- [ ] Write unit tests: `tests/test_news_fetcher.py` (pending)

## Phase 2: Processing & Summarisation (Week 2)

### 2.1 Article Processing
- [x] Implement `src/news/processor.py` — `process(raw_articles, keyword_id)`: dedup by SHA-256(url), relevance filter, call `ArticleStore.save()`
- [x] Add optional RAG ingestion path: call `PageIndexStore.ingest()` when `config.news.ingest_into_rag=true`
- [ ] Write unit tests: `tests/test_news_processor.py` (pending)

### 2.2 Summarisation
- [x] Implement `src/news/summariser.py` — `summarise(article, llm_wrapper)`: build prompt, call `llm_wrapper.generate()`, parse response, call `ArticleStore.save_summary()`
- [x] Implement `summarise_pending(article_store, llm_wrapper)`: batch process all `is_summarised=0` articles
- [x] Handle LLM failure: retry once, fall back to `"[Summary unavailable]"`
- [ ] Write unit tests: `tests/test_news_summariser.py` (pending)

### 2.3 News Service Facade
- [x] Implement `src/news/news_service.py` — `NewsService` class: `run_for_keyword(keyword_id)`, `run_all()`, `fetch_now(keyword_id)`, `get_articles(keyword_id, page, limit)`
- [x] Expose `NewsService` instance to `app_state["news_service"]`

## Phase 3: Scheduler (Week 2–3)

### 3.1 Background Scheduler
- [x] Implement `src/news/scheduler.py` — APScheduler-backed `NewsScheduler`: `start()`, `stop()`, `register_keyword(keyword)`, `remove_keyword(keyword_id)`, `refresh()`
- [x] On scheduler start, load all enabled keywords and register jobs
- [x] On keyword create/update/delete, update scheduler jobs in real time
- [x] Wire scheduler start into `startup_event` in `src/api/app.py`
- [x] Wire scheduler stop into `shutdown_event`

### 3.2 Retention Cleanup
- [x] Add `ArticleStore.delete_older_than(days: int) -> CleanupResult` — collect `rag_doc_ids` first, then `DELETE WHERE fetched_at < cutoff`; `article_summaries` removed via CASCADE
- [x] Add `NewsService.run_startup_cleanup()` — calls `delete_older_than(config.news.retention_days)` and purges returned `rag_doc_ids` from `PageIndexStore`
- [x] Call `news_service.run_startup_cleanup()` in `startup_event`; log `deleted` and `rag_purged` counts
- [x] Register fixed-interval APScheduler job `id="news_retention_cleanup"` (default 6h)
- [ ] Write unit tests: `tests/test_news_retention.py` (pending)

## Phase 4: API Routes (Week 3)

### 4.1 Keywords Endpoints
- [x] Implement `src/api/news_routes.py`:
  - `GET  /api/keywords`
  - `POST /api/keywords`
  - `PATCH /api/keywords/{id}`
  - `DELETE /api/keywords/{id}`
  - `POST /api/keywords/{id}/fetch-now`
- [x] Include `news_router` in `app.py`
- [ ] Write API integration tests: `tests/test_news_api.py` (pending)

### 4.2 Articles Endpoints
- [x] Add to `src/api/news_routes.py`:
  - `GET  /api/news?keyword_id=&page=&limit=`
  - `GET  /api/news/{article_id}`
  - `POST /api/news/{article_id}/summarize`
  - `DELETE /api/news/{article_id}`
  - `POST /api/news/{article_id}/translate` *(bonus: LLM-powered summary translation)*
  - `GET  /api/news/translation-languages`
  - `GET  /api/news/status`
  - `POST /api/keywords/suggest` *(bonus: LLM-powered keyword suggestion)*
- [x] Return unified `ArticleWithSummary` response shape

## Phase 5: Frontend — News Page (Week 4)

### 5.1 API Client
- [x] Add `frontend/src/api/newsApi.ts` — typed functions: `getKeywords()`, `createKeyword()`, `updateKeyword()`, `deleteKeyword()`, `fetchNow()`, `getArticles()`, `resummarize()`, `deleteArticle()`, `translateSummary()`, `getTranslationLanguages()`

### 5.2 Keyword Management Components
- [x] Create `frontend/src/components/news/KeywordForm.tsx` — 2-step describe → review form, interval selector, LLM keyword suggestion
- [x] Create `frontend/src/components/news/KeywordCard.tsx` — status badge, last-fetched, toggle, delete (ConfirmDialog), inline edit, +N new-article badge
- [x] Create `frontend/src/components/news/KeywordPanel.tsx` — form + list of `KeywordCard`, background polling every 60s

### 5.3 Article Feed Components
- [x] Create `frontend/src/components/news/ArticleCard.tsx` — title (opens detail modal), source badge, published date, collapsible summary, retention badge, external link, ConfirmDialog delete, toast, translate
- [x] Create `frontend/src/components/news/ArticleFeed.tsx` — search/filter/sort toolbar, pagination, background new-article polling + banner, mobile hamburger
- [x] Create `frontend/src/components/news/ArticleDetailModal.tsx` — `<dialog>` modal, desktop 2-col, mobile tabbed
- [x] Create `frontend/src/components/shared/ConfirmDialog.tsx` — accessible `<dialog>` with aria-labelledby, focus management, backdrop click

### 5.4 News Page & Routing
- [x] Create `frontend/src/components/NewsPage.tsx` — `ToastProvider` + `TranslationProvider`, desktop sidebar, mobile slide-in overlay with hamburger + backdrop
- [x] Add `"News"` nav item to the sidebar in `App.tsx`
- [x] Add route handler for `NewsPage` in `App.tsx`
- [ ] Write basic smoke tests for `KeywordForm` and `ArticleCard` (pending)

## Phase 6: Polish & Integration (Week 5)

### 6.1 End-to-End Integration
- [x] Enable `news.enabled: true` in dev config; pipeline working end-to-end
- [x] Verified fetch cycle working via server logs (articles fetched + summarised on schedule)
- [x] Verified retention cleanup runs on startup (logs show `removed 0 articles older than 3 days`)
- [ ] Verify RAG ingestion path (pending)
- [ ] Verify periodic cleanup interval manually (pending)

### 6.2 Error & Edge Cases
- [x] Display "No articles yet — click Fetch Now" when keyword has no articles
- [x] Show error toast when Fetch Now fails (network/API error)
- [x] Gracefully handle summarisation partial failure (show partial results + skeleton)
- [x] Confirm retention cleanup DB failure is logged but does not crash the server
- [ ] Handle `newsapi_key` missing: disable the fetch button in UI, show setup prompt (pending)
- [ ] Confirm RAG purge failure on expired article is logged but does not crash cleanup (pending)

### 6.3 Documentation & Config
- [x] Add `newsapi-python` and `apscheduler` to `requirements.txt`
- [ ] Add `NEWSAPI_KEY` env var to `.env.example` (pending)
- [ ] Document news feature in `README.md` (pending)

## Dependencies

```
newsapi-python>=0.2.7
apscheduler>=3.10.0
```
