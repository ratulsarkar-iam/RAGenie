# Keyword Manager UI Specification

## Overview

The Keyword Manager is a left-sidebar panel that lets users track, configure, pause, and delete news keywords. Every action provides immediate optimistic feedback (local state updated before API confirms) with toast notifications and graceful rollback on failure.

## Component: `KeywordPanel`

### Layout
```
┌────────────────────────────────┐
│ Tracked Keywords     [+ Add ▼] │  ← header row
├────────────────────────────────┤
│ ▼ [KeywordForm — slide-down]   │  ← visible when "+ Add" clicked
├────────────────────────────────┤
│ [KeywordCard] Narendra Modi    │
│ [KeywordCard] PyTorch 2.0      │
│ [KeywordCard] Climate Change   │
├────────────────────────────────┤
│ (empty state if no keywords)   │
└────────────────────────────────┘
```

### Props / State
```typescript
// Reads from NewsContext — no local data fetching needed
const { keywords, keywordsLoading } = useContext(NewsContext);
```

---

## Component: `KeywordForm`

### Behaviour
- Slides down below the header with a `max-h` CSS transition (200 ms).
- Clicking "+ Add" again while form is open collapses it.
- Form resets on successful submission.

### Fields

| Field | Type | Default | Validation |
|---|---|---|---|
| `term` | text input | "" | Required; 1–200 chars; trimmed |
| `fetch_interval_minutes` | `<select>` | 60 | One of: 15, 30, 60, 120, 360, 1440 |
| `max_articles_per_fetch` | `<select>` | 10 | One of: 5, 10, 20, 50 |

### Error States
- Empty term → inline `"Keyword cannot be empty"` below input; submit blocked
- 409 from API → inline `"Already tracking this keyword"`
- 422 from API → inline `"Invalid value"`
- Generic error → toast `error` notification

### Accessibility
- `<form>` with `aria-label="Add keyword"`
- `<label>` elements linked to all inputs via `htmlFor`
- Submit button `aria-busy="true"` while pending

---

## Component: `KeywordCard`

### Visual anatomy

```
●  Narendra Modi                          ← StatusDot + TermLabel
   60 min · 10 articles · 2h ago         ← MetaRow
   ⚠ "Rate limit exceeded"               ← ErrorBadge (conditional)
   [↓ Fetch Now] [⏸ Pause] [✎ Edit] [🗑] ← actions
```

### StatusDot colours

| State | Colour | Meaning |
|---|---|---|
| `enabled=true`, `last_error=null` | Green | Active, last fetch succeeded |
| `enabled=true`, `last_error!=null` | Amber | Active but last fetch failed |
| `enabled=false` | Grey | Paused |

### Actions

#### Fetch Now
- Calls `triggerFetchNow(id)`.
- Button shows spinner, disabled for 3 s.
- Toast: `"Fetching news for '{term}'…"` (info).
- On next poll if `last_fetched_at` updated: toast `"Fetched N articles for '{term}'"` (success).
- On next poll if `last_error` set: toast `"Fetch failed for '{term}': {error}"` (error).

#### Pause / Resume
- Calls `updateKeyword(id, { enabled: !kw.enabled })`.
- Optimistic: `StatusDot` switches colour immediately.
- Rollback on API error + toast `error`.
- `aria-label`: `"Pause {term}"` / `"Resume {term}"`.

#### Edit → `KeywordEditDrawer`
Slide-down panel replacing the MetaRow:
```
Fetch interval:    [select]
Max articles:      [select]
              [Save]  [Cancel]
```
- Pre-filled with current values.
- Save calls `updateKeyword(id, patch)` + success toast.
- Cancel closes drawer; no changes.
- `aria-expanded="true/false"` on the Edit button.
- Focus moves to first select when drawer opens.

#### Delete
- Opens a `<dialog>` modal (not `window.confirm`):
  ```
  Delete keyword "Narendra Modi"?
  This will also delete all 47 stored articles.
  [Cancel]  [Delete]
  ```
- Dialog has focus trap; `Escape` = Cancel.
- On confirm: calls `deleteKeyword(id)`.
- Optimistic removal from list; rollback + error toast on failure.
- `aria-label="Delete {term} keyword"` on delete button.

### Loading Skeleton — `KeywordCardSkeleton`
```
○  ████████████ (w-32 grey bar)
   ███ · ██ · ████ (w-8 / w-6 / w-12 grey bars)
   [  ] [  ] [  ] [  ]  (4 placeholder buttons)
```
Shown 3× while `keywordsLoading=true`.

---

## State Transitions

```
                  ┌──────────────────────────┐
    add keyword   │  enabled=true            │  pause
   ─────────────► │  last_error=null         │ ──────────►  enabled=false
                  │  StatusDot: GREEN        │
                  └─────────────┬────────────┘
                                │ fetch fails
                                ▼
                  ┌──────────────────────────┐
                  │  enabled=true            │  fetch succeeds
                  │  last_error="..."        │ ─────────────►  (back to green)
                  │  StatusDot: AMBER        │
                  └──────────────────────────┘
```

---

## Testing

| Test | Expected |
|---|---|
| Submit empty `KeywordForm` | Inline error shown; no API call |
| Submit valid form | `createKeyword` called; card appears; form cleared |
| Duplicate keyword (409) | Inline error "Already tracking this keyword" |
| Pause toggle | `updateKeyword` called with `{ enabled: false }`; dot turns grey |
| Delete confirm modal closes on Escape | No API call; modal gone; focus returns to delete button |
| Delete confirmed | Card removed optimistically; `deleteKeyword` called |
| `KeywordEditDrawer` save | `updateKeyword` called with new values; drawer closes; toast shown |
| Error badge shown | When `last_error != null`, `⚠` icon visible with tooltip text |
