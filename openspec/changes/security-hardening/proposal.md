# Security Hardening — Gap Mitigations

## Overview

This change addresses all findings from the code-audit performed on the RAGenie codebase. Gaps are split across three phases by severity so each batch can be reviewed and shipped independently.

## Problem Statement

The codebase has meaningful security scaffolding (audit logger, rate limiting, file validation, prompt-injection guards, SSRF checks) but several structural gaps undermine the overall posture:

- **Auth enforcement is absent** — `auth.enabled=true` is set in config but the `require_auth` dependency is wired to zero business endpoints. Any unauthenticated HTTP client can read memories, upload documents, execute tasks, and drive MCP tools.
- **Shared-singleton orchestrator** — all HTTP requests and WebSocket connections share one `ChatOrchestrator` instance whose `conversation` field mutates without a lock, enabling race conditions and cross-user context leakage.
- **Double user-message bug** — in the WebSocket agent path the user message is added to conversation history twice (manually at line 131, then again inside `achat()`), corrupting multi-turn context.
- **Two runtime `AttributeError`s** in `seed_news_server` — wrong type passed to `connect_server()` and a call to a non-existent `get_tools_for_server()` method.
- **Internal error details exposed** — raw `str(e)` returned in HTTP 500 responses leaks file paths, model names, and stack info.
- **Proactive background task not cancelled** on graceful shutdown, keeping the event loop alive.
- **Rate limit config silently ignored** — `SecurityConfig.rate_limiting` values are never passed to `RateLimitMiddleware`, which hardcodes its own tiers.
- **Non-atomic RAG index write** — a crash mid-write leaves a truncated JSON file; next startup raises `DocumentStoreError`.
- **Input size limits absent** on memory, feedback, and MCP-chat request models.
- Several low-severity quality/deprecation issues.

## Non-Goals

- Encrypting MCP credentials at rest (scope for a separate `secret-store` change).
- Per-session orchestrator refactor (listed as Phase 2 design work; auth coverage is the higher priority).
- WebSocket JWT handshake at upgrade time (requires frontend coordination; tracked separately).
- Redis-backed rate limiting for multi-worker deployments.

## Benefits

- All existing authenticated endpoints remain protected; new `require_auth_when_enabled` dependency respects `auth.enabled` flag so development deployments (auth disabled) still work without tokens.
- Runtime bugs in `seed_news_server` are eliminated.
- Conversation history integrity is restored for agent-mode WebSocket.
- RAG index survives process crashes.
- Config-driven rate limits take effect without code changes.

## Phases

| Phase | Priority | Scope |
|---|---|---|
| 1 — Critical | 🔴 | Auth wiring, double-message bug, seed_news bugs, shutdown task, error leakage, input limits |
| 2 — Medium | 🟠 | Atomic RAG write, config-driven rate limits |
| 3 — Low | 🟡 | datetime deprecation, import placement, streaming delay, CSP, CORS tightening |
