# Multi-User Platform: Auth Enforcement, Per-User Data Isolation & Activity Logging

## Overview

This proposal converts RAGenie from a single-tenant app (auth is an optional on/off gate) into a true **multi-user platform**. Every user gets their own isolated news keywords, MCP server configurations, and a full activity log of what they searched, chatted about, and did in the app. The frontend gains a Login/Register page and an Activity page.

## Problem Statement

RAGenie already has a JWT-based auth system (`src/auth/user_store.py`, `src/api/auth_routes.py`), but it is **not multi-tenant**:

- `require_auth_when_enabled` (`src/auth/dependencies.py`) only checks *"is a valid token present"* — it never scopes data by `user_id`. When `auth.enabled=false` (the default), there is no login at all.
- The `keywords` table (`src/news/keyword_store.py`) has a **globally unique** `term_lower` column. Today, if user A creates keyword "IPL", no other user could ever create "IPL" — this directly contradicts the requirement that two users can independently manage distinct AND overlapping keyword sets (e.g. both create "NASA").
- The `mcp_servers` table (`src/mcp_client/server_store.py`) has the same global-uniqueness problem on `name`, and `MCPClientManager` (`src/mcp_client/manager.py`) holds one global in-memory connection/tool registry shared by all requests — there is no concept of "whose server this is."
- There is no queryable **activity log**. `src/security/audit_logger.py` only writes security events (rate-limit hits, blocked uploads) to a rotating file — it is not user-attributed and not designed for product-analytics style querying (e.g. "show me everything user A did").
- The frontend (`frontend/src/`) has **no login/register UI at all** — no `AuthContext`, no protected routes, no way to log in through the browser.

## Proposed Solution

Six tightly-scoped changes, layered so each can be implemented and tested independently:

1. **Auth Enforcement** — Flip auth from optional to mandatory for all data-owning endpoints; every request resolves a `current_user`, and JWTs carry `sub=user_id`. A one-time migration assigns all pre-existing (pre-migration) keywords/servers/conversations to the first-registered (admin) user so nothing is silently lost.

2. **Keyword Isolation** — Add `user_id` to the `keywords` table; uniqueness constraint becomes `(user_id, term_lower)`. All list/get/due queries scope by `user_id`. This directly satisfies: user A creates "IPL", user B creates "BPL", and both A and B can independently create "NASA".

3. **MCP Server Isolation** — Add `user_id` to the `mcp_servers` table; uniqueness becomes `(user_id, name)`. `MCPClientManager` becomes user-scoped (one manager instance — or one partition of its registries — per `user_id`), so tool discovery/dispatch never leaks across users.

4. **Activity Log** — New `src/activity/` module: SQLite-backed `ActivityStore` + `ActivityLogger` service, capturing chat messages, searches, keyword CRUD, article fetches, MCP tool calls, document uploads, and login/logout events, each attributed to `user_id`. REST endpoints for self-service viewing and an admin all-users view.

5. **Frontend Auth UI** — `AuthContext` (token storage, login/register/logout, axios interceptor for `Authorization` header), a Login/Register page, and route-gating in `App.tsx` so the app is inaccessible without a session.

6. **Frontend Activity UI** — A new "Activity" page (own history, filterable by event type/date) styled consistently with the existing Tailwind + `ThemeContext` dark/light theme, plus an admin variant to browse all users' activity.

## Non-Goals

- Fine-grained per-resource sharing/permissions (e.g. user A sharing a keyword with user B). Out of scope for v1 — data is strictly private per user.
- SSO / OAuth / social login. Email+password via the existing `UserStore` remains the only auth method.
- Real-time activity streaming (e.g. WebSocket live feed). The Activity page polls/refetches on demand.
- Rewriting the existing security audit logger — it continues to serve its distinct purpose (security events, not user activity).

## Benefits

- **True multi-tenancy** — each user's keywords, MCP servers, and history are private and independently manageable.
- **Product visibility** — full picture of what each user does in the app, queryable per-user or system-wide (admin).
- **No data loss** — existing single-user data is migrated to the first admin account, not deleted.
- **Consistent UX** — new Login and Activity pages reuse the existing design system (Tailwind, `ThemeContext`, `Sidebar` navigation patterns).

## Implementation Strategy

Six specs cover the full scope:

| Spec | What it covers |
|---|---|
| `auth-enforcement` | Mandatory auth, JWT `user_id` propagation, conversation ownership, data migration to admin user |
| `keyword-isolation` | `user_id` column + composite uniqueness on `keywords`; scoped CRUD/scheduler |
| `mcp-server-isolation` | `user_id` column + composite uniqueness on `mcp_servers`; per-user `MCPClientManager` scoping |
| `activity-log` | `ActivityStore`/`ActivityLogger`, event taxonomy, REST API (self + admin) |
| `frontend-auth-ui` | `AuthContext`, Login/Register page, protected routing, API client auth header |
| `frontend-activity-ui` | Activity page (self view + admin view), Sidebar integration |
