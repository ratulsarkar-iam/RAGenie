# News Dashboard (Frontend) Specification

## Overview

A dedicated **News** page added to the existing RAGenie frontend. The page has two zones: a **Keyword Panel** for managing tracked terms, and an **Article Feed** for browsing and reading AI-generated summaries. It integrates seamlessly with the existing React + TypeScript + TailwindCSS + Lucide stack.

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | React 18 + TypeScript |
| Styling | TailwindCSS (existing, no new libraries) |
| Icons | `lucide-react` (existing) |
| HTTP | `axios` (existing, via `src/api/`) |
| Routing | State-based (existing App.tsx pattern) |
| Auto-refresh | `setInterval` hook (5-minute polling) |

## Page Layout

```
┌─────────────────────────────────────────────────────────────┐
│  [Sidebar nav]  │              News                          │
│                 │                                            │
│  ◉ Chat         │ ┌──────────────┐  ┌──────────────────────┐ │
│  ○ Documents    │ │ Keywords     │  │ Articles             │ │
│  ◉ News         │ │              │  │                      │ │
│  ○ Analytics    │ │ [+ Add]      │  │ [Filter dropdown]    │ │
│                 │ │              │  │                      │ │
│                 │ │ ● Modi       │  │ ┌──────────────────┐ │ │
│                 │ │   60m  10art │  │ │ Title of article │ │ │
│                 │ │   [⏸][🗑]    │  │ │ BBC · 2h ago     │ │ │
│                 │ │              │  │ │ ▼ AI Summary      │ │ │
│                 │ │ ○ PyTorch    │  │ │   3-line summary  │ │ │
│                 │ │   (paused)   │  │ │ [Read full →]    │ │ │
│                 │ │   [▶][🗑]    │  │ └──────────────────┘ │ │
│                 │ └──────────────┘  │                      │ │
│                 │                  │ [Load more]          │ │
│                 │                  └──────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## Components

### `src/api/newsApi.ts`

```typescript
export interface Keyword {
  id: string;
  term: string;
  enabled: boolean;
  fetch_interval_minutes: number;
  max_articles_per_fetch: number;
  created_at: string;
  last_fetched_at: string | null;
  article_count: number;
  last_error: string | null;
}

export interface ArticleWithSummary {
  id: string;
  keyword_id: string;
  title: string;
  content: string;
  url: string;
  source: string;
  published_at: string | null;
  fetched_at: string;
  summary: string | null;     // null = not yet summarised
  summary_model: string | null;
}

export const getKeywords = (): Promise<Keyword[]>
export const createKeyword = (data: Partial<Keyword>): Promise<Keyword>
export const updateKeyword = (id: string, data: Partial<Keyword>): Promise<Keyword>
export const deleteKeyword = (id: string): Promise<void>
export const fetchNow = (id: string): Promise<void>
export const getArticles = (params: { keyword_id?: string; page: number; limit: number }): Promise<ArticleWithSummary[]>
export const resummarize = (article_id: string): Promise<ArticleWithSummary>
export const deleteArticle = (article_id: string): Promise<void>
```

### `KeywordForm` — `src/components/news/KeywordForm.tsx`

```
Props: onCreated: (kw: Keyword) => void

Renders:
  <input placeholder="e.g. Narendra Modi" />
  <select> 15m | 30m | 1h | 2h | 6h | 24h </select>
  <select> 5 | 10 | 20 | 50 articles </select>
  <button> + Add Keyword </button>

State: term, fetchInterval, maxArticles, loading, error
```

- Validates `term` is non-empty before submitting.
- Disables button and shows spinner during submission.
- Shows inline error on 409 (already exists) or 422.

### `KeywordCard` — `src/components/news/KeywordCard.tsx`

```
Props: keyword: Keyword, onUpdated, onDeleted, onFetchNow

Renders:
  • Keyword term (bold)
  • Status badge: green "Active" / grey "Paused"
  • Last fetched: "2 hours ago" (relative time) or "Never"
  • Article count badge
  • Error indicator (red ⚠ icon) if last_error != null
  • Actions: [Pause/Resume toggle] [Fetch Now] [Delete]
```

- "Fetch Now" button shows spinner for 2 s then re-fetches keyword list.
- Delete triggers a `window.confirm` before calling API.
- Pause/Resume calls `PATCH /api/keywords/{id}` with `{ enabled: !keyword.enabled }`.

### `KeywordPanel` — `src/components/news/KeywordPanel.tsx`

```
State: keywords[], loading, showForm

Renders:
  <h2>Tracked Keywords</h2>
  <button onClick={() => setShowForm(true)}>+ Add</button>
  {showForm && <KeywordForm />}
  {keywords.map(kw => <KeywordCard ... />)}
  {keywords.length === 0 && <EmptyState />}
```

### `ArticleCard` — `src/components/news/ArticleCard.tsx`

```
Props: article: ArticleWithSummary

Renders:
  • Title (linked to article.url, opens in new tab)
  • Source badge + published relative time
  • "AI Summary" section (collapsible, default open):
      - If summary != null: summary text
      - If summary == null: "Summarising…" skeleton
      - [Regenerate] icon button (calls resummarize())
  • [Read full article →] external link
```

- Summary section uses a smooth `max-h` TailwindCSS transition for collapse/expand.
- Articles without summaries show an animated skeleton (3 grey lines).

### `ArticleFeed` — `src/components/news/ArticleFeed.tsx`

```
State: articles[], selectedKeywordId, page, hasMore, loading

Renders:
  <FilterBar>
    <select> All Keywords | [keyword terms] </select>
    <span>{total} articles</span>
  </FilterBar>
  {loading && <SkeletonList />}
  {articles.map(a => <ArticleCard ... />)}
  {hasMore && <button>Load more</button>}
  {!loading && articles.length === 0 && <EmptyState />}
```

- Auto-refreshes every 5 minutes via `setInterval`.
- Resets `page=1` and `articles=[]` when `selectedKeywordId` changes.

### `NewsPage` — `src/components/NewsPage.tsx`

```typescript
export function NewsPage() {
  return (
    <div className="flex gap-6 h-full">
      <aside className="w-72 shrink-0">
        <KeywordPanel />
      </aside>
      <main className="flex-1 overflow-y-auto">
        <ArticleFeed />
      </main>
    </div>
  );
}
```

## Routing Integration

In `App.tsx`, add `"news"` as a valid view and render `<NewsPage />`:

```typescript
// In the view state union:
type View = "chat" | "documents" | "analytics" | "news";

// In the nav sidebar:
<NavItem icon={<Newspaper size={18} />} label="News" view="news" />

// In the render switch:
{view === "news" && <NewsPage />}
```

Use `<Newspaper />` icon from `lucide-react`.

## Empty & Error States

| State | UI |
|---|---|
| No keywords added | "Add your first keyword above to start tracking news." |
| Keyword has no articles | "No articles yet — click Fetch Now to start." |
| `last_error` on keyword | Red warning icon with tooltip showing the error message |
| `NEWSAPI_KEY` not set | Yellow banner: "News API key not configured. See README." |
| Network error on load | "Failed to load. Retry?" button |

## Configuration / Feature Flag

When `config.news.enabled=false`, the backend returns `503` for all `/api/keywords` and `/api/news` routes. The frontend detects this and hides the "News" nav item to avoid showing a broken page.

## Testing Strategy

### Component Tests
- `KeywordForm`: submit with empty term shows validation error; successful submit calls `createKeyword` and invokes `onCreated`.
- `KeywordCard`: clicking delete calls `window.confirm` then `deleteKeyword`.
- `ArticleCard`: "AI Summary" section expands/collapses on click.

### Integration / E2E
- Full flow: add keyword → fetch now → articles appear in feed with summaries.
- Disable keyword → "Paused" badge shown, no more scheduled fetches.
