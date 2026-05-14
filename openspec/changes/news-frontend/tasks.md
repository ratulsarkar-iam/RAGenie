# News Frontend — Implementation Tasks

## Phase 1: Foundation (Day 1–2)

### 1.1 API Client
- [x] Create `frontend/src/api/newsApi.ts` — `Keyword`, `ArticleWithSummary`, `KeywordCreate` types
- [x] Implement `getKeywords()`, `createKeyword()`, `updateKeyword()`, `deleteKeyword()`, `triggerFetchNow()`
- [x] Implement `getArticles(filters)`, `resummarize(id)`, `deleteArticle(id)`
- [x] Add `getNewsStatus()` → `GET /api/news/status` (returns `{ enabled: boolean }`) for feature-flag check

### 1.2 Shared State & Hooks
- [ ] Create `frontend/src/contexts/NewsContext.tsx` — `NewsContextValue` interface + provider *(deferred; state kept local per component)*
- [ ] Implement `useKeywords.ts` *(deferred; logic inline in KeywordPanel)*
- [ ] Implement `useArticles.ts` *(deferred; logic inline in ArticleFeed)*
- [ ] Implement `useNewsPolling.ts` *(deferred; polling inline in ArticleFeed/KeywordPanel)*
- [x] Implement `useRetentionCountdown` — inline `retentionBadge()` in `ArticleCard`; amber 6–12h, red <6h
- [x] Implement `useToast` — `ToastContext.tsx` with `ToastProvider` + built-in `ToastContainer`

### 1.3 Toast Container
- [x] Create `frontend/src/components/shared/ToastContainer.tsx` — built into `ToastProvider`
- [x] Fixed bottom-right, auto-dismiss 4 s, supports success / error / info variants
- [x] Mount `<ToastProvider />` in `NewsPage.tsx`

## Phase 2: Keyword Management (Day 2–3)

### 2.1 KeywordForm
- [x] Create `KeywordForm.tsx` — 2-step (describe → LLM suggest → review & save); term input, interval select, max-articles select
- [x] Validate: non-empty term; disable submit while loading
- [x] Show inline error for 409 (duplicate) and 422 (validation)
- [x] On success: call `onCreated(kw)`, clear form, show success toast

### 2.2 KeywordCard
- [x] Create `KeywordCard.tsx` — status dot, term, meta row (count / interval / last-fetched), actions
- [x] `StatusDot`: enabled/disabled badge; amber `⚠` icon on `last_error`
- [x] "Last fetched" displayed as relative time (`"2h ago"` / `"Never"`)
- [x] `ErrorBadge`: amber `⚠` icon with `title` tooltip showing `last_error` text
- [x] Pause/Resume toggle: calls `updateKeyword({ enabled: !kw.enabled })` + toast
- [x] Fetch Now button: calls `triggerFetchNow(id)`, shows spinner, shows info toast
- [x] Delete button: opens `ConfirmDialog` (`<dialog>`-based), on confirm calls `deleteKeyword(id)` + toast
- [x] Edit button: inline term + interval editing (replaces term row with inputs)

### 2.3 KeywordEditDrawer
- [x] Inline editing in `KeywordCard` — term + interval pre-filled; save/cancel buttons; Enter to save, Escape to cancel *(drawer approach replaced with inline)*

### 2.4 KeywordPanel
- [x] Create `KeywordPanel.tsx` — header with "+ Add" toggle, `KeywordForm` (collapsed by default), `KeywordList`
- [x] Skeleton placeholder while loading
- [x] `KeywordEmptyState` — empty state shown when no keywords
- [x] Per-keyword `+N` new-article badge (background polling every 60s; clears on keyword select)

## Phase 3: Article Feed (Day 3–5)

### 3.1 ArticleToolbar
- [x] Toolbar built into `ArticleFeed` — search input, time filter, status filter, sort pills, article count
- [x] Search: full-text filter across title/summary/source; clear button when non-empty
- [x] Sort: Newest Added / Newest Published / Most Relevant
- [x] Filters: time (Today/3d/7d) + status (All/Summarised/Pending)

### 3.2 RetentionBadge
- [x] `RetentionBadge` inline in `ArticleCard` via `retentionBadge()` helper
- [x] Hidden when > 12h remain; amber (6–12h); red (<6h)
- [x] `role="status"` + visible text label

### 3.3 SummarySection
- [x] `SummarySection` inline in `ArticleCard` — collapsible, default open
- [x] `summary == null`: animated skeleton (3 grey lines)
- [x] `summary != null`: text + Regenerate + Translate buttons
- [x] `max-h` transition; `aria-expanded` / `aria-controls` on toggle button

### 3.4 ArticleCard
- [x] Create `ArticleCard.tsx` — `RetentionBadge`, source badge, published time, title button, `SummarySection`, external link
- [x] Title/Expand click → `onOpenDetail(article)` → opens `ArticleDetailModal`
- [x] Delete via `ConfirmDialog` (`<dialog>`-based) + toast
- [x] `aria-label` on all icon buttons
- [x] `aria-expanded` / `aria-controls` on summary toggle

### 3.5 ArticleDetailModal
- [x] Create `ArticleDetailModal.tsx` — `aria-modal="true"`, Escape to close, click-outside to close
- [x] Desktop: two-column (summary left, full content right)
- [x] Mobile: tabs ("AI Summary" / "Full Content")
- [x] Header: title, source, date, external link, close button
- [x] Regenerate button calls `resummarize(id)` + success toast

### 3.6 ArticleSection & ArticleGrid
- [x] `ArticleFeed` composes toolbar + article list + load-more + empty states
- [x] "Load more" button with spinner
- [x] Empty state variants: no articles / no search results
- [x] New-article banner (background poll every 60s) with Load button

## Phase 4: NewsPage & Routing (Day 5)

### 4.1 NewsPage
- [x] Create `NewsPage.tsx` — wraps in `ToastProvider` + `TranslationProvider`
- [x] Desktop layout: `<aside w-72> KeywordPanel </aside> <main flex-1> ArticleFeed </main>`
- [x] Mobile layout: `KeywordPanel` hidden by default; hamburger in `ArticleFeed` header shows it as slide-in overlay with backdrop
- [x] `ArticleDetailModal` mounted here; `detailArticle` state passed down as `onOpenDetail`

### 4.2 App.tsx integration
- [x] Added `"news"` to `View` type union
- [x] Added `<NavItem icon={<Newspaper />} label="News" view="news" />` to sidebar
- [x] Added `{view === "news" && <NewsPage />}` to render switch

## Phase 5: Polish (Day 6)

### 5.1 Responsive & Mobile
- [ ] Test keyword panel bottom sheet on viewport < 640 px
- [ ] Verify `ArticleDetailModal` goes full-screen on mobile
- [ ] Verify `ArticleGrid` collapses to single column on narrow screens

### 5.2 Accessibility Audit
- [x] All icon buttons have `aria-label` in `KeywordCard` and `ArticleCard`
- [x] Delete confirm uses `ConfirmDialog` (`<dialog>` element, `aria-modal`, `aria-labelledby`)
- [x] `ArticleDetailModal` uses `<dialog>` element, `aria-modal="true"`, Escape closes
- [ ] Run axe-core audit (pending)

### 5.3 Edge Cases & Final QA
- [x] Empty DB: "No keywords yet" state renders correctly
- [x] No articles match search: "No articles match the current filters" empty state with clear button
- [x] Article near expiry (< 6 h): red RetentionBadge visible via `retentionBadge()` helper
- [x] Rapid keyword toggle: button disabled during pending API call
- [ ] Network offline toast (pending)
- [ ] After backend cleanup, deleted articles disappear on next 5-min poll (verified manually)

### 5.4 Tests
- [ ] `useRetentionCountdown`: returns correct label and `isExpiringSoon` flag for edge cases
- [ ] `RetentionBadge`: hidden when > 12 h; amber 6–12 h; red < 6 h
- [ ] `KeywordForm`: empty submit shows error; success fires `onCreated`
- [ ] `KeywordCard`: delete confirm flow; pause/resume toggle
- [ ] `ArticleCard`: summary collapse/expand; modal opens on title click
- [ ] `ArticleDetailModal`: closes on Escape; focus trap works
- [ ] `ArticleToolbar`: search filters articles; sort changes order
