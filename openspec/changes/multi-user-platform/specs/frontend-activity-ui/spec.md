# Spec: frontend-activity-ui

## Purpose

Give every user a page to review their own activity history, and give admins a way to inspect any user's activity — styled consistently with the rest of the app (Tailwind, `ThemeContext`, existing list/pagination patterns from `SearchHistoryPanel.tsx`).

## Modules

- `frontend/src/api/activityApi.ts` (new)
- `frontend/src/components/ActivityPage.tsx` (new)
- `frontend/src/components/Sidebar.tsx` (modified — new nav item)
- `frontend/src/App.tsx` (modified — route/section wiring)

## Public Interface

```typescript
// activityApi.ts
interface ActivityEvent {
  id: string;
  user_id: string;
  event_type: string;
  description: string;
  metadata: Record<string, unknown> | null;
  created_at: string;
}

export function listMyActivity(params: {
  event_type?: string;
  page?: number;
  limit?: number;
}): Promise<{ items: ActivityEvent[]; total: number }>;

export function listAllActivity(params: {
  user_id?: string;
  event_type?: string;
  page?: number;
  limit?: number;
}): Promise<{ items: ActivityEvent[]; total: number }>;
```

## Behavior

- `ActivityPage` default view: current user's own feed, newest first, grouped by day (date header separators).
- Each row shows: an icon/badge derived from `event_type`, the `description` text, a relative timestamp (e.g. "3m ago"), and — if present — a small expandable `metadata` detail (JSON pretty-printed on click).
- Filter controls: dropdown for `event_type` (populated from the known taxonomy, plus an "All" option), and a text search box that filters `description` client-side on the currently loaded page (server-side search is out of scope for v1).
- Pagination: "Load more" button appends the next page (`page += 1`), consistent with the incremental-load pattern already used for search history.
- Admin-only: if `user.role === "admin"`, an additional user-picker dropdown (populated from `GET /api/auth/users`, already existing) appears at the top; selecting a user switches the data source from `listMyActivity` to `listAllActivity({ user_id })`. A "My Activity" option resets to the self view.
- New "Activity" entry added to `Sidebar.tsx`'s navigation list, following the existing icon + label pattern used for "News", "MCP Servers", etc. Visible to all authenticated users (the admin user-picker is inside the page, not a separate nav entry).

## Validation Rules

- `event_type` filter dropdown only allows values from the known taxonomy (`ActivityEventType`); "All" sends no filter param.
- Admin user-picker is hidden entirely for non-admin users (`user.role !== "admin"`), not merely disabled.

## Error Behavior

- API failure while loading the feed shows an inline retry state (reuse existing empty/error-state patterns from `NewsPage.tsx` or `SearchHistoryPanel.tsx`).
- Empty feed (no events yet) shows a friendly empty-state message, not a blank screen.

## Tests / Verification

- Manual: perform a handful of instrumented actions (create a keyword, send a chat message, upload a document) and confirm each appears in `ActivityPage` shortly after (on next "Load more"/refresh).
- Manual: as a non-admin user, confirm the admin user-picker is absent.
- Manual: as an admin, switch between "My Activity" and another user's activity; confirm data source changes accordingly and no cross-user data leaks into the wrong view.
- Manual: dark/light theme toggle renders `ActivityPage` correctly in both modes.
