# Article Feed UI Specification

## Overview

The Article Feed is the main content area of the News page. It displays fetched articles with their AI summaries, retention countdown badges, filtering/search/sort controls, and provides access to a full-detail modal. Articles are loaded with pagination and auto-refreshed every 5 minutes.

---

## Component: `ArticleToolbar`

### Layout
```
┌─────────────────────────────────────────────────────────────────┐
│ 🔍 [Search articles…]  [All Keywords ▾]  [Newest ▾]  47 articles│
└─────────────────────────────────────────────────────────────────┘
```

### Controls

| Control | Type | Behaviour |
|---|---|---|
| Search input | `<input type="search">` | Filters client-side on `title`, `summary`, `source`; clears on × button |
| Keyword filter | `<select>` | "All Keywords" + one entry per tracked keyword; synced with `NewsContext.selectedKeywordId` |
| Sort | `<select>` | "Newest first" (default) / "Oldest first" / "Source A–Z" |
| Article count | `<span>` | Shows filtered count: `"47 articles"` or `"3 of 47"` when search is active |

Toolbar state is owned by `NewsContext` so that clicking a `KeywordCard` in the sidebar automatically filters the feed (sets `selectedKeywordId`).

---

## Component: `RetentionBadge`

### Logic (from `useRetentionCountdown`)
```typescript
const expiresAt = new Date(article.fetched_at).getTime() + 3 * 86_400_000;
const msLeft = expiresAt - Date.now();
const hoursLeft = Math.floor(msLeft / 3_600_000);
```

| `hoursLeft` | Badge text | Tailwind classes |
|---|---|---|
| > 12 | Hidden | — |
| 6–12 | `"Expires in Xh"` | `bg-amber-50 text-amber-700 ring-1 ring-amber-200` |
| 1–6 | `"Expires in Xh"` | `bg-red-50 text-red-700 ring-1 ring-red-200` |
| < 1 | `"Expires in <1h"` | same red style |

Badge is always text-labelled (not colour-only). `role="status"` so screen readers announce it.

---

## Component: `ArticleCard`

### Full anatomy

```
┌────────────────────────────────────────────────────────┐
│ [RetentionBadge]  [BBC News badge]          2h ago  [⋮]│  ← header row
│                                                        │
│ Ukraine ceasefire talks enter third day               │  ← title (button → opens modal)
│                                                        │
│ ▼ AI Summary                                          │  ← SummarySection toggle
│   Three-sentence abstractive summary from Ollama...   │
│   [↺ Regenerate]                                      │
│                                                        │
│                          [Read full article →]        │  ← external link
└────────────────────────────────────────────────────────┘
```

### Title click behaviour
- Clicking the title text opens `ArticleDetailModal` (via `NewsContext.openDetail(article)`).
- `"Read full article →"` is a separate `<a target="_blank">` link that goes directly to the source URL.

### ArticleCard Menu (⋮)
A `<button>` with `aria-label="Article options"` opens a small dropdown:
```
[ Delete article ]
```
Delete calls `deleteArticle(id)` after a single-step confirmation toast:
`"Article removed"` (undo not required).

### `SummarySection` toggle

| `summary` value | Rendered content |
|---|---|
| `null` | Animated skeleton (3 grey bars, pulse animation) |
| `"[Summary unavailable]"` | Grey italic text + "Regenerate" button |
| Any other string | Summary text + small "↺" regenerate icon button |

Toggle state: default `open=true`; persists in component local state (not context).
`aria-expanded`, `aria-controls` wired to the content div.

Regenerate button:
- Calls `resummarize(article.id)`.
- Shows spinner in place of ↺ icon while pending.
- On success: summary text updates in-place; toast `"Summary updated"` (success).
- On failure: toast `"Could not regenerate summary"` (error).

### `ArticleCardSkeleton`
```
┌────────────────────────────────────────────────────┐
│  ████ (w-12)          ████████████████  (w-24)     │
│  ████████████████████████████  (w-full, h-5)       │
│  ████████████████████  (w-3/4, h-4)                │
│  █████████████████████████████████  (w-full, h-3)  │
│  ████████████████  (w-2/3, h-3)                    │
└────────────────────────────────────────────────────┘
```
Shown while `articlesLoading=true` for the first page.

---

## Component: `ArticleDetailModal`

### Trigger
- Clicking an `ArticleCard` title.
- `NewsContext.detailArticle` stores the selected article.

### Layout

**Desktop (≥ 768 px):**
```
┌─────────────────────────────────────────────────────────────────┐
│  Ukraine ceasefire talks...  [BBC News]  May 10, 2025  [× Close]│
├────────────────────────┬────────────────────────────────────────┤
│  AI Summary            │  Full Article                          │
│                        │                                        │
│  Three-sentence        │  Full article text (scrollable,        │
│  summary from          │  truncated to max_content_chars)       │
│  Ollama…               │                                        │
│                        │                                        │
│  [↺ Regenerate]        │  [Read full article at BBC News →]     │
└────────────────────────┴────────────────────────────────────────┘
```

**Mobile (< 768 px):**
```
Full-screen modal
┌─────────────────────────┐
│ Title…          [× Close]│
├─────────────────────────┤
│ [Summary] [Full Article] │  ← tab row
├─────────────────────────┤
│  Tab content (scrollable)│
└─────────────────────────┘
```

### Accessibility
- `role="dialog"`, `aria-modal="true"`, `aria-labelledby="modal-title"`
- Focus moves to the close button on open; `Escape` triggers close
- Focus trap: Tab/Shift+Tab cycle within modal
- On close: focus returns to the triggering `ArticleCard` title element

### Close behaviour
- `×` button, `Escape` key, or clicking the backdrop (outside modal content area) closes it.
- Calls `NewsContext.closeDetail()`.

---

## Pagination & Loading

### Initial Load
1. `useArticles` fetches `page=1, limit=20` from API.
2. Shows 3× `ArticleCardSkeleton` while loading.
3. Renders cards once loaded.

### Load More
- "Load more" button at bottom of feed.
- Calls `loadMore()` from `useArticles` (fetches next page, appends to list).
- Button shows spinner while next page loads.
- When `hasMore=false`: replace button with `"You've seen all articles"`.

### Auto-refresh (5 min)
- `useNewsPolling` calls `refresh()` which re-fetches `page=1`.
- New articles prepended to top of list.
- If new articles found: toast `"N new articles available"` (info).
- No full re-render of existing cards.

---

## Empty States

| Condition | Primary message | Secondary / CTA |
|---|---|---|
| No keywords added | "No keywords yet" | "Add a keyword in the panel to start tracking news." |
| Keyword active, no articles | "No articles fetched yet" | "Click **Fetch Now** on a keyword to get started." |
| Search returns no results | "No results for '{query}'" | "Try a different search term." |
| All keywords paused | "All keywords are paused" | "Resume a keyword to fetch new articles." |
| Network error on load | "Couldn't load articles" | [Retry button] |

---

## Testing

| Test | Expected |
|---|---|
| Search filters cards client-side | Only matching cards rendered; count updates |
| Keyword filter select → selects keyword | Only that keyword's articles shown |
| Sort "Oldest first" | Cards re-ordered; oldest `fetched_at` at top |
| `RetentionBadge` hidden (> 12 h) | No badge element rendered |
| `RetentionBadge` amber (6–12 h) | Badge with correct text and amber classes |
| `RetentionBadge` red (< 6 h) | Badge with correct text and red classes |
| `SummarySection` toggle | `aria-expanded` flips; content visibility toggles |
| Summary `null` → skeleton shown | 3 skeleton bars rendered |
| Regenerate button success | Summary text updated; success toast shown |
| `ArticleDetailModal` opens on title click | `detailArticle` set; modal rendered |
| `ArticleDetailModal` closes on Escape | `closeDetail()` called; focus returns to card |
| Delete from ⋮ menu | `deleteArticle` called; card removed from list |
| Load more | Next page fetched; new cards appended |
| Auto-refresh adds new articles | Toast shown; new cards at top |
