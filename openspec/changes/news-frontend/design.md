# News Frontend — Design Document

## Component Tree

```
NewsPage
├── NewsContext.Provider          ← shared state: keywords[], articles[], filters
│
├── KeywordPanel                  ← left sidebar (w-72, collapsible on mobile)
│   ├── KeywordPanelHeader
│   │   ├── Title "Tracked Keywords"
│   │   └── AddButton → opens KeywordForm (inline slide-down)
│   ├── KeywordForm               ← add new keyword (collapsible)
│   │   ├── TermInput
│   │   ├── IntervalSelect
│   │   ├── MaxArticlesSelect
│   │   └── SubmitButton
│   ├── KeywordList
│   │   └── KeywordCard[]
│   │       ├── StatusDot         ← green/grey/red
│   │       ├── TermLabel
│   │       ├── MetaRow           ← article count, last fetched, interval
│   │       ├── ErrorBadge        ← shown when last_error != null
│   │       ├── KeywordActions
│   │       │   ├── FetchNowButton
│   │       │   ├── PauseResumeToggle
│   │       │   ├── EditButton    → opens KeywordEditDrawer
│   │       │   └── DeleteButton
│   │       └── KeywordEditDrawer ← inline settings form (slide-down)
│   └── KeywordEmptyState
│
└── ArticleSection                ← main area (flex-1)
    ├── ArticleToolbar
    │   ├── SearchInput           ← client-side full-text filter
    │   ├── KeywordFilterSelect   ← "All" or specific keyword
    │   ├── SortSelect            ← Newest | Oldest | Source A-Z
    │   └── ArticleCount          ← "47 articles"
    ├── ArticleGrid               ← responsive grid
    │   └── ArticleCard[]
    │       ├── RetentionBadge    ← "Expires in Xh" when < 12h remain
    │       ├── SourceBadge
    │       ├── PublishedTime     ← relative ("2h ago")
    │       ├── Title             ← external link
    │       ├── SummarySection    ← collapsible
    │       │   ├── SummaryText or SummarySkeleton
    │       │   └── RegenerateButton
    │       ├── ReadMoreLink
    │       └── ArticleCardMenu   ← ⋮ → Delete article
    ├── LoadMoreButton / EndOfFeedMessage
    └── ArticleEmptyState
```

`ArticleDetailModal` is mounted at `NewsPage` level and triggered by clicking an `ArticleCard` title:
```
ArticleDetailModal
├── ModalHeader (title, source, date, keyword tag, close)
├── SummaryPanel      ← left half on desktop
│   ├── "AI Summary" heading
│   ├── SummaryText
│   └── RegenerateButton
└── ContentPanel      ← right half on desktop (scrollable)
    ├── FullArticleContent (truncated to max_content_chars)
    └── ReadFullArticleLink
```

## Shared State — `NewsContext`

```typescript
interface NewsContextValue {
  // Keywords
  keywords: Keyword[];
  keywordsLoading: boolean;
  createKeyword: (data: KeywordCreate) => Promise<void>;
  updateKeyword: (id: string, patch: Partial<Keyword>) => Promise<void>;
  deleteKeyword: (id: string) => Promise<void>;
  triggerFetchNow: (id: string) => Promise<void>;

  // Articles
  articles: ArticleWithSummary[];
  articlesLoading: boolean;
  hasMore: boolean;
  loadMore: () => void;

  // Filters (controlled here so both toolbar and keyword panel stay in sync)
  selectedKeywordId: string | null;
  setSelectedKeywordId: (id: string | null) => void;
  searchQuery: string;
  setSearchQuery: (q: string) => void;
  sortOrder: "newest" | "oldest" | "source";
  setSortOrder: (s: SortOrder) => void;

  // Modal
  detailArticle: ArticleWithSummary | null;
  openDetail: (article: ArticleWithSummary) => void;
  closeDetail: () => void;
}
```

`NewsContext` is created in `src/contexts/NewsContext.tsx` and wraps `NewsPage`.

## Custom Hooks

### `useKeywords()`
```typescript
// Fetches keyword list, exposes mutators that call newsApi and update context
function useKeywords(): {
  keywords: Keyword[];
  loading: boolean;
  error: string | null;
  create: (data: KeywordCreate) => Promise<Keyword>;
  update: (id: string, patch: Partial<Keyword>) => Promise<Keyword>;
  remove: (id: string) => Promise<void>;
  fetchNow: (id: string) => Promise<void>;
  refresh: () => void;
}
```

### `useArticles(filters)`
```typescript
function useArticles(filters: ArticleFilters): {
  articles: ArticleWithSummary[];   // filtered + sorted client-side
  loading: boolean;
  hasMore: boolean;
  loadMore: () => void;
  resummarize: (articleId: string) => Promise<void>;
  remove: (articleId: string) => Promise<void>;
}
```

### `useNewsPolling(intervalMs)`
```typescript
// Runs refresh() on keywords and loadMore(page=1) on articles every intervalMs
function useNewsPolling(intervalMs: number = 5 * 60 * 1000): void
```

### `useRetentionCountdown(fetchedAt, retentionDays)`
```typescript
// Returns { label: "Expires in 3h", isExpiringSoon: boolean }
// isExpiringSoon = true when < 12 hours remain
// Updates every minute via setInterval
function useRetentionCountdown(
  fetchedAt: string,
  retentionDays: number = 3
): { label: string; isExpiringSoon: boolean }
```

### `useToast()`
```typescript
// Provides { show(message, type) } — renders in a ToastContainer fixed at bottom-right
function useToast(): { show: (message: string, type: "success" | "error" | "info") => void }
```

## Retention Countdown UI

Articles fetched ≥ 72 h ago are deleted by the backend. The frontend surfaces this so users know an article is nearing expiry:

| Time remaining | Badge | Colour |
|---|---|---|
| > 12 h | Hidden | — |
| 6–12 h | "Expires in Xh" | Amber (`text-amber-600 bg-amber-50`) |
| < 6 h | "Expires in Xh" | Red (`text-red-600 bg-red-50`) |
| Negative (just expired, waiting for cleanup) | Hidden | — |

The countdown uses `fetched_at` from the API response:
```typescript
const expiresAt = new Date(article.fetched_at).getTime() + retentionDays * 86400000;
const remaining = expiresAt - Date.now();
```

## Article Search (Client-Side)

Applied after articles are fetched, before render:
```typescript
const filtered = articles.filter(a =>
  !searchQuery ||
  a.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
  a.summary?.toLowerCase().includes(searchQuery.toLowerCase()) ||
  a.source.toLowerCase().includes(searchQuery.toLowerCase())
);
```

No debounce needed (in-memory operation on ≤ 200 items).

## Sort Logic

```typescript
const sorted = [...filtered].sort((a, b) => {
  if (sortOrder === "newest")
    return new Date(b.fetched_at).getTime() - new Date(a.fetched_at).getTime();
  if (sortOrder === "oldest")
    return new Date(a.fetched_at).getTime() - new Date(b.fetched_at).getTime();
  if (sortOrder === "source")
    return a.source.localeCompare(b.source);
  return 0;
});
```

## Responsive Layout

| Breakpoint | Layout |
|---|---|
| `< sm` (< 640 px) | Keyword panel hidden; hamburger icon opens it as a bottom sheet |
| `sm – lg` (640–1024 px) | Keyword panel collapses to icon-only sidebar (w-12) |
| `≥ lg` (≥ 1024 px) | Full side-by-side layout (`w-72` panel + flex-1 feed) |

`ArticleDetailModal` is full-screen on mobile, centered overlay on desktop.

## Accessibility

- All buttons have `aria-label` (e.g., `aria-label="Pause Narendra Modi keyword"`).
- `KeywordCard` delete button shows a `<dialog>`-based confirm modal (not `window.confirm`) with focus trap.
- `ArticleDetailModal` traps focus; `Escape` closes it; `aria-modal="true"`.
- `SummarySection` toggle uses `aria-expanded` and `aria-controls`.
- `SearchInput` has `role="search"` wrapper and `aria-label="Search articles"`.
- `RetentionBadge` uses `role="status"` so screen readers announce updates.
- Colour-only status indicators (StatusDot, RetentionBadge) have visible text labels.

## Toast Notifications

Shown at bottom-right, auto-dismiss after 4 s:

| Event | Message | Type |
|---|---|---|
| Keyword created | "Tracking '{term}'" | success |
| Keyword deleted | "Stopped tracking '{term}'" | info |
| Fetch Now triggered | "Fetching news for '{term}'…" | info |
| Fetch Now completed (polled) | "{N} new articles fetched" | success |
| Fetch Now failed (`last_error`) | "Fetch failed: {error}" | error |
| Summary regenerated | "Summary updated" | success |
| Article deleted | "Article removed" | info |
| Network error | "Connection error — retrying in 5 min" | error |

## File Structure

```
frontend/src/
├── api/
│   └── newsApi.ts              ← typed API client
├── contexts/
│   └── NewsContext.tsx         ← shared state provider
├── hooks/
│   ├── useKeywords.ts
│   ├── useArticles.ts
│   ├── useNewsPolling.ts
│   ├── useRetentionCountdown.ts
│   └── useToast.ts
└── components/
    ├── news/
    │   ├── NewsPage.tsx
    │   ├── KeywordPanel.tsx
    │   ├── KeywordForm.tsx
    │   ├── KeywordCard.tsx
    │   ├── KeywordEditDrawer.tsx
    │   ├── ArticleSection.tsx
    │   ├── ArticleToolbar.tsx
    │   ├── ArticleCard.tsx
    │   ├── ArticleDetailModal.tsx
    │   ├── RetentionBadge.tsx
    │   ├── SummarySection.tsx
    │   └── skeletons/
    │       ├── KeywordCardSkeleton.tsx
    │       └── ArticleCardSkeleton.tsx
    └── shared/
        └── ToastContainer.tsx  ← if not already present
```
