# News Frontend — Management & Viewer UI

## Overview

A dedicated, implementation-ready frontend plan for the News Aggregator feature. Where `news-aggregator/specs/news-dashboard/spec.md` gives a component sketch, this plan provides the full design: component hierarchy, shared state, custom hooks, detailed UX interactions, retention countdown, inline editing, article search, and accessibility requirements.

## What this plan adds beyond the existing dashboard sketch

| Area | Existing sketch | This plan |
|---|---|---|
| Retention | Not covered | "Expires in X" badge; amber warning when < 12 h remain |
| Keyword editing | Delete only | Inline interval/article-count editing, settings drawer |
| Article search | Not covered | Client-side full-text search across loaded articles |
| Article sort | Not covered | Sort by date, source, keyword |
| Article detail | Card only | Expandable modal with full content + summary side-by-side |
| State management | Local state per component | `NewsContext` sharing keywords + articles across panels |
| Custom hooks | Not covered | `useKeywords`, `useArticles`, `useNewsPolling` |
| Notifications | Not covered | Toast system for fetch success/failure, cleanup events |
| Loading states | Mentioned (skeleton) | Full skeleton specs for every component |
| Accessibility | Not covered | ARIA labels, keyboard navigation, focus management |
| Responsive | Not covered | Mobile-first breakpoints, collapsible keyword panel |

## Non-Goals

- Implementing the backend API (covered in `news-aggregator`).
- Building a standalone app — this is a new page inside the existing RAGenie frontend.
- Adding new npm dependencies (uses the existing React + TailwindCSS + Lucide + Axios stack).

## Success Criteria

- User can add, pause, resume, edit, and delete keywords without a page reload.
- User can browse, search, and filter articles; each article shows its AI summary and a retention countdown.
- Any article fetching or deletion event produces a visible toast notification.
- All interactive elements are keyboard-accessible.
- The page works on screens ≥ 320 px wide.
