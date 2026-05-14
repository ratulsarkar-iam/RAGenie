# News Aggregator & Summarizer for RAGenie

## Overview

This proposal adds a keyword-driven news aggregation and summarisation capability to RAGenie. Users define a set of tracked keywords; the system periodically fetches relevant news articles from the web, stores them, and generates concise LLM-powered summaries — all surfaced through a dedicated **News** page in the existing frontend.

## Problem Statement

RAGenie is a powerful local knowledge assistant, but its knowledge is limited to documents the user has manually uploaded. It has no awareness of current events or breaking news. Users who want to stay informed on specific topics currently have no way to:

- Track live news for a given topic or keyword.
- Get concise summaries without reading full articles.
- Ask questions across a corpus of recent news (via existing RAG chat).
- Manage what topics to follow from within the app.

## Proposed Solution

Implement three tightly integrated subsystems:

1. **Keyword Manager** — A dedicated CRUD interface (API + UI page) where users add, pause, and remove tracked keywords (e.g., "Narendra Modi", "PyTorch 2.0", "climate change"). Each keyword can have a configurable fetch interval.

2. **News Pipeline** — A background service that, for each active keyword, fetches articles from a News API (NewsAPI.org recommended), deduplicates, filters for relevance, persists to a local SQLite database, and optionally ingests article content into the RAG index for chat-based Q&A.

3. **Summariser** — Leverages RAGenie's existing Ollama LLM (via the `LangChainLLM` wrapper) to generate abstractive summaries for each stored article. No external model downloads are required.

## Non-Goals

- Real-time streaming of news (polling is sufficient).
- Social media or video content (text articles only).
- Paid / gated news sources.
- Multi-user keyword segregation (single-user app).

## Benefits

- Extends RAGenie from a static document store into a live knowledge assistant.
- Zero additional model dependencies — uses the already-running Ollama LLM.
- All data stays local (SQLite, local RAG index).
- Modular — each subsystem can be developed and shipped independently.
- Foundation for proactive briefings (integrates with the existing `ProactiveEngine`).

## Implementation Strategy

Each of the three subsystems maps to an independent module that can be enabled/disabled via `config.yaml`. The five specs below cover the full scope:

| Spec | What it covers |
|---|---|
| `keyword-management` | Keyword CRUD, scheduling config, pause/resume |
| `news-retrieval` | NewsAPI integration, fetch loop, pagination, error handling |
| `article-processing` | Deduplication, relevance filtering, SQLite storage, RAG ingestion |
| `summarization` | LLM prompt design, batch summarisation, retry logic |
| `news-dashboard` | React UI page: keyword manager + article feed with summaries |
