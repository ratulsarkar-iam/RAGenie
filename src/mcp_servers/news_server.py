"""RAGenie News MCP Server — exposes news keyword and article tools via FastMCP.

Run as a stdio MCP server (register this in the app's MCP Servers page):
  Command : python
  Args    : -m src.mcp_servers.news_server
  Env     : RAGENIE_API_URL=http://localhost:8000   (optional, default shown)

Or using an absolute path:
  Command : python
  Args    : /absolute/path/to/src/mcp_servers/news_server.py
"""
import json
import os
import sys

import httpx
from mcp.server.fastmcp import FastMCP

_BASE = os.environ.get("RAGENIE_API_URL", "http://localhost:8000").rstrip("/")
_TIMEOUT = 30.0

mcp = FastMCP(
    "RAGenie News",
    instructions=(
        "Tools for managing news keywords and reading aggregated news articles "
        "from the RAGenie news aggregator. Use create_news_keyword to track a topic, "
        "list_news_keywords to see what is being monitored, get_news_articles to read "
        "the latest fetched articles, and update/delete tools to manage keywords."
    ),
)


def _get(path: str, **params) -> dict | list:
    with httpx.Client(timeout=_TIMEOUT) as client:
        r = client.get(f"{_BASE}{path}", params={k: v for k, v in params.items() if v is not None})
    r.raise_for_status()
    return r.json()


def _post(path: str, body: dict | None = None) -> dict:
    with httpx.Client(timeout=_TIMEOUT) as client:
        r = client.post(f"{_BASE}{path}", json=body or {})
    r.raise_for_status()
    return r.json()


def _patch(path: str, body: dict) -> dict:
    with httpx.Client(timeout=_TIMEOUT) as client:
        r = client.patch(f"{_BASE}{path}", json=body)
    r.raise_for_status()
    return r.json()


def _delete(path: str) -> dict:
    with httpx.Client(timeout=_TIMEOUT) as client:
        r = client.delete(f"{_BASE}{path}")
    r.raise_for_status()
    return r.json()


def _resolve_keyword_id(term: str) -> tuple[str, str] | None:
    """Resolve a human term to (keyword_id, keyword_term) via the REST API.

    Tries, in order:
      1. Exact match (case-insensitive)
      2. Substring match (term inside keyword, or keyword inside term)
    Returns (id, term) on success or None.
    """
    try:
        keywords = _get("/api/keywords")
    except Exception:
        return None
    if not keywords:
        return None
    term_lower = term.strip().lower()
    # 1. Exact
    for kw in keywords:
        if kw["term"].lower() == term_lower:
            return kw["id"], kw["term"]
    # 2. Substring
    for kw in keywords:
        if term_lower in kw["term"].lower() or kw["term"].lower() in term_lower:
            return kw["id"], kw["term"]
    return None


# ── Tools ─────────────────────────────────────────────────────────────────────

@mcp.tool()
def list_news_keywords() -> str:
    """List all tracked news keywords with their fetch interval, article count,
    last fetch time, and enabled status.

    Returns a JSON array of keyword objects.
    """
    try:
        keywords = _get("/api/keywords")
        if not keywords:
            return "No keywords are being tracked yet. Use create_news_keyword to add one."
        lines = []
        for kw in keywords:
            status = "active" if kw.get("enabled") else "paused"
            last = kw.get("last_fetched_at") or "never"
            lines.append(
                f"- [{status}] \"{kw['term']}\" (id={kw['id'][:8]}…) | "
                f"interval={kw['fetch_interval_minutes']}min | "
                f"articles={kw['article_count']} | last_fetched={last}"
            )
        return "\n".join(lines)
    except httpx.HTTPStatusError as e:
        return f"Error fetching keywords: {e.response.status_code} {e.response.text}"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def create_news_keyword(
    term: str,
    fetch_interval_minutes: int = 60,
    max_articles_per_fetch: int = 10,
) -> str:
    """Create a new news keyword to track.

    Args:
        term: The search term / topic to monitor (e.g. "IPL 2025", "AI regulation").
        fetch_interval_minutes: How often to fetch new articles (min 5, max 1440). Default 60.
        max_articles_per_fetch: Maximum articles to fetch per cycle (1–100). Default 10.

    Returns a confirmation with the new keyword's ID.
    """
    if fetch_interval_minutes < 5 or fetch_interval_minutes > 1440:
        return "fetch_interval_minutes must be between 5 and 1440."
    if max_articles_per_fetch < 1 or max_articles_per_fetch > 100:
        return "max_articles_per_fetch must be between 1 and 100."
    try:
        kw = _post("/api/keywords", {
            "term": term,
            "fetch_interval_minutes": fetch_interval_minutes,
            "max_articles_per_fetch": max_articles_per_fetch,
        })
        return (
            f"Keyword created: \"{kw['term']}\" (id={kw['id']}) | "
            f"fetching every {kw['fetch_interval_minutes']} min."
        )
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 409:
            return f"Keyword \"{term}\" already exists."
        return f"Error creating keyword: {e.response.status_code} {e.response.text}"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def update_news_keyword(
    keyword_id: str,
    term: str | None = None,
    fetch_interval_minutes: int | None = None,
    max_articles_per_fetch: int | None = None,
    enabled: bool | None = None,
) -> str:
    """Update an existing news keyword's settings.

    Args:
        keyword_id: The full ID of the keyword to update (from list_news_keywords).
        term: New search term (optional).
        fetch_interval_minutes: New fetch interval in minutes (optional, 5–1440).
        max_articles_per_fetch: New article limit per fetch (optional, 1–100).
        enabled: Set to false to pause fetching, true to resume.

    Returns confirmation of the updated keyword.
    """
    patch: dict = {}
    if term is not None:
        patch["term"] = term
    if fetch_interval_minutes is not None:
        patch["fetch_interval_minutes"] = fetch_interval_minutes
    if max_articles_per_fetch is not None:
        patch["max_articles_per_fetch"] = max_articles_per_fetch
    if enabled is not None:
        patch["enabled"] = enabled
    if not patch:
        return "No fields to update — provide at least one of: term, fetch_interval_minutes, max_articles_per_fetch, enabled."
    try:
        kw = _patch(f"/api/keywords/{keyword_id}", patch)
        status = "active" if kw.get("enabled") else "paused"
        return (
            f"Updated: \"{kw['term']}\" (id={kw['id']}) | "
            f"interval={kw['fetch_interval_minutes']}min | status={status}"
        )
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return f"Keyword id={keyword_id} not found."
        return f"Error updating keyword: {e.response.status_code} {e.response.text}"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def delete_news_keyword(keyword_id: str) -> str:
    """Delete a news keyword and stop tracking it.

    Args:
        keyword_id: The full ID of the keyword to delete (from list_news_keywords).

    Returns a confirmation message.
    """
    try:
        _delete(f"/api/keywords/{keyword_id}")
        return f"Keyword id={keyword_id} deleted successfully."
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return f"Keyword id={keyword_id} not found."
        return f"Error deleting keyword: {e.response.status_code} {e.response.text}"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def fetch_news_now(keyword: str) -> str:
    """Trigger an immediate news fetch for a keyword (does not wait for next interval).

    Args:
        keyword: The keyword term to fetch now (e.g. 'IPL', 'Modi'). Plain text — not an ID.

    Returns confirmation that the fetch has been enqueued.
    """
    resolved = _resolve_keyword_id(keyword)
    if resolved is None:
        try:
            kws = _get("/api/keywords")
            known = ", ".join(f'"{k["term"]}"' for k in kws) if kws else "none"
        except Exception:
            known = "(could not fetch)"
        return f"No tracked keyword found matching '{keyword}'. Tracked keywords: {known}."
    kid, kterm = resolved
    try:
        _post(f"/api/keywords/{kid}/fetch-now")
        return f"Fetch enqueued for '{kterm}'. New articles will appear shortly."
    except httpx.HTTPStatusError as e:
        return f"Error: {e.response.status_code} {e.response.text}"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def get_news_articles(
    keyword: str | None = None,
    query: str | None = None,
    page: int = 1,
    limit: int = 10,
) -> str:
    """Retrieve fetched news articles by topic/keyword name.

    Args:
        keyword: Topic or keyword name (e.g. 'IPL', 'Trump Modi war'). Plain text — not an ID.
                 Leave empty to return articles from all tracked keywords.
        query:   Optional free-text search within the returned articles.
        page:    Page number (default 1).
        limit:   Articles per page (1–100, default 10).

    Returns a formatted list of articles with title, source, published date, and summary.
    """
    resolved_id: str | None = None
    resolved_term: str | None = None

    if keyword and keyword.strip():
        resolved = _resolve_keyword_id(keyword.strip())
        if resolved is None:
            try:
                kws = _get("/api/keywords")
                known = ", ".join(f'"{k["term"]}"' for k in kws) if kws else "none"
            except Exception:
                known = "(could not fetch)"
            return (
                f"No tracked keyword found matching '{keyword}'. "
                f"Tracked keywords: {known}. "
                f"Use create_news_keyword to start tracking it."
            )
        resolved_id, resolved_term = resolved

    try:
        articles = _get("/api/news", keyword_id=resolved_id, page=page, limit=limit)

        # Optional free-text filter
        if query and query.strip():
            q = query.strip().lower()
            articles = [
                a for a in articles
                if q in (a.get("title") or "").lower()
                or q in (a.get("summary") or a.get("content") or "").lower()
            ]

        if not articles:
            hint = f" for '{resolved_term or keyword}'" if (keyword and keyword.strip()) else ""
            return (
                f"No articles found{hint}. "
                f"Use fetch_news_now with keyword='{resolved_term or keyword}' to trigger a fetch."
            )

        label = f"'{resolved_term}'" if resolved_term else "all keywords"
        parts = [f"Latest news for {label} ({len(articles)} article(s)):\n"]
        for i, a in enumerate(articles, 1):
            pub = a.get("published_at") or "unknown"
            summary = a.get("summary") or a.get("content") or "(no content)"
            summary = summary[:300] + "…" if len(summary) > 300 else summary
            parts.append(
                f"[{i}] {a['title']}\n"
                f"    Source: {a.get('source', 'unknown')} | Published: {pub}\n"
                f"    {summary}\n"
                f"    URL: {a.get('url', '')}"
            )
        return "\n\n".join(parts)
    except httpx.HTTPStatusError as e:
        return f"Error fetching articles: {e.response.status_code} {e.response.text}"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def suggest_news_keyword(description: str) -> str:
    """Use the LLM to suggest an optimised news search term from a natural-language description.

    Args:
        description: A natural-language topic description, e.g. "cricket matches in India 2025".

    Returns the suggested keyword term and recommended fetch interval.
    """
    try:
        result = _post("/api/keywords/suggest", {"description": description})
        return json.dumps(result, ensure_ascii=False, indent=2)
    except httpx.HTTPStatusError as e:
        return f"Error: {e.response.status_code} {e.response.text}"
    except Exception as e:
        return f"Error: {e}"


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run(transport="stdio")
