"""MCP tool definitions and handlers for RAGenie.

Tools served through the /mcp and /sse endpoints:
  - Built-in: search_documents, search_web, list_documents, ask_ragenie, execute_task
  - News    : list_news_keywords, create_news_keyword, update_news_keyword,
              delete_news_keyword, fetch_news_now, get_news_articles, suggest_news_keyword

External MCP-client server tools are NOT forwarded here to avoid circular duplication
when the app is registered as its own MCP client.
"""

import json
import asyncio
from typing import Any, Dict, List, Optional
from ..core.logging_config import get_logger

logger = get_logger(__name__)

# ── Dependency injection ───────────────────────────────────────────────────────
# Populated by app.py during startup via set_dependencies()

_rag_store = None
_search_service = None
_orchestrator = None
_task_engine = None
_news_service = None
_mcp_client_manager = None


def set_dependencies(
    rag_store=None,
    search_service=None,
    orchestrator=None,
    task_engine=None,
    news_service=None,
    mcp_client_manager=None,
):
    global _rag_store, _search_service, _orchestrator, _task_engine
    global _news_service, _mcp_client_manager
    _rag_store = rag_store
    _search_service = search_service
    _orchestrator = orchestrator
    _task_engine = task_engine
    _news_service = news_service
    _mcp_client_manager = mcp_client_manager


# ── Tool schemas ───────────────────────────────────────────────────────────────

TOOLS: List[Dict[str, Any]] = [
    {
        "name": "search_documents",
        "description": (
            "Search through RAGenie's indexed documents using BM25 keyword search. "
            "Returns the most relevant document chunks for the given query."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query"
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of results to return (default 5)",
                    "default": 5
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "search_web",
        "description": (
            "Search the web using DuckDuckGo for real-time information. "
            "Use this for current events, facts not in the document index, or live data."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The web search query"
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum results to return (default 5)",
                    "default": 5
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "list_documents",
        "description": "List all documents currently indexed in RAGenie with their metadata.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "ask_ragenie",
        "description": (
            "Ask RAGenie a question using the full RAG pipeline: retrieves relevant "
            "document context and generates an LLM-powered answer."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The question to ask"
                },
            },
            "required": ["question"],
        },
    },
    {
        "name": "execute_task",
        "description": (
            "Execute a natural language task such as creating a reminder, scheduling a "
            "meeting, or saving a note. Requires the task engine to be enabled."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "request": {
                    "type": "string",
                    "description": "Plain English task description"
                },
            },
            "required": ["request"],
        },
    },
]


# ── Tool handlers ──────────────────────────────────────────────────────────────

async def _handle_search_documents(args: Dict[str, Any]) -> str:
    if _rag_store is None:
        return "RAG store not available."
    query = args["query"]
    top_k = int(args.get("top_k", 5))
    try:
        results = _rag_store.search(query, top_k=top_k)
        if not results:
            return f"No documents found for query: '{query}'"
        lines = [f"Found {len(results)} result(s) for '{query}':\n"]
        for i, doc in enumerate(results, 1):
            title = getattr(doc, "filename", getattr(doc, "doc_id", f"doc-{i}"))
            content = ""
            if hasattr(doc, "chunks") and doc.chunks:
                content = doc.chunks[0].content[:400]
            elif hasattr(doc, "content"):
                content = str(doc.content)[:400]
            lines.append(f"{i}. **{title}**\n{content}")
        return "\n\n".join(lines)
    except Exception as e:
        logger.error(f"search_documents failed: {e}")
        return f"Search error: {e}"


async def _handle_search_web(args: Dict[str, Any]) -> str:
    if _search_service is None:
        return "Web search service not available."
    query = args["query"]
    max_results = int(args.get("max_results", 5))
    try:
        results = _search_service.search(query, max_results=max_results)
        if results:
            lines = [f"Web search results for '{query}':\n"]
            for i, r in enumerate(results, 1):
                lines.append(f"{i}. **{r.title}**\n{r.url}\n{r.snippet}")
            return "\n\n".join(lines)
        # DuckDuckGo returned empty (rate-limited) — fall back to LLM knowledge
        if _orchestrator is not None:
            logger.warning(f"search_web: DuckDuckGo returned empty for '{query}', falling back to LLM knowledge")
            import asyncio
            loop = asyncio.get_event_loop()
            def _llm_fallback():
                _orchestrator.start_conversation("mcp-search-fallback")
                return _orchestrator.chat_simple(f"Answer this question using your knowledge (web search unavailable): {query}")
            return await loop.run_in_executor(None, _llm_fallback)
        return f"No web results found for: '{query}'. DuckDuckGo is rate-limiting — try again in a moment."
    except Exception as e:
        logger.error(f"search_web failed: {e}")
        return f"Web search error: {e}"


async def _handle_list_documents(args: Dict[str, Any]) -> str:
    if _rag_store is None:
        return "RAG store not available."
    try:
        docs = _rag_store.list_documents()
        if not docs:
            return "No documents are currently indexed."
        lines = [f"Indexed documents ({len(docs)} total):\n"]
        for i, doc in enumerate(docs, 1):
            filename = getattr(doc, "filename", getattr(doc, "doc_id", f"doc-{i}"))
            chunks = len(doc.chunks) if hasattr(doc, "chunks") else "?"
            lines.append(f"{i}. {filename}  ({chunks} chunks)")
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"list_documents failed: {e}")
        return f"Error listing documents: {e}"


async def _handle_ask_ragenie(args: Dict[str, Any]) -> str:
    if _orchestrator is None:
        return "RAGenie orchestrator not available."
    question = args["question"]
    try:
        import asyncio
        loop = asyncio.get_event_loop()
        def _run():
            _orchestrator.start_conversation("mcp-tool")
            return _orchestrator.chat_simple(question)
        response = await loop.run_in_executor(None, _run)
        return response if isinstance(response, str) else str(response)
    except Exception as e:
        logger.error(f"ask_ragenie failed: {e}")
        return f"Error: {e}"


async def _handle_execute_task(args: Dict[str, Any]) -> str:
    if _task_engine is None:
        return "Task engine not available (tasks.enabled=false in config)."
    request = args["request"]
    try:
        result = await _task_engine.execute_task(request)
        status = "✓" if result.success else "✗"
        return f"{status} {result.summary}\n{json.dumps(result.details, indent=2) if result.details else ''}"
    except Exception as e:
        logger.error(f"execute_task failed: {e}")
        return f"Task error: {e}"


# ── News tool schemas ──────────────────────────────────────────────────────────

_NEWS_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "list_news_keywords",
        "description": "List all tracked news keywords with fetch interval, article count, and last fetch time.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "create_news_keyword",
        "description": "Create a new news keyword to track. Automatically starts fetching on the configured interval.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "term": {"type": "string", "description": "Search term / topic to monitor"},
                "fetch_interval_minutes": {"type": "integer", "description": "Fetch interval in minutes (5–1440)", "default": 60},
                "max_articles_per_fetch": {"type": "integer", "description": "Max articles per cycle (1–100)", "default": 10},
            },
            "required": ["term"],
        },
    },
    {
        "name": "update_news_keyword",
        "description": "Update an existing news keyword's term, interval, article limit, or enabled state.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "keyword_id": {"type": "string", "description": "Keyword ID (from list_news_keywords)"},
                "term": {"type": "string"},
                "fetch_interval_minutes": {"type": "integer"},
                "max_articles_per_fetch": {"type": "integer"},
                "enabled": {"type": "boolean"},
            },
            "required": ["keyword_id"],
        },
    },
    {
        "name": "delete_news_keyword",
        "description": "Delete a news keyword and stop tracking it.",
        "inputSchema": {
            "type": "object",
            "properties": {"keyword_id": {"type": "string", "description": "Keyword ID to delete"}},
            "required": ["keyword_id"],
        },
    },
    {
        "name": "fetch_news_now",
        "description": "Trigger an immediate news fetch for a keyword without waiting for the next interval.",
        "inputSchema": {
            "type": "object",
            "properties": {"keyword": {"type": "string", "description": "Keyword term to fetch now (e.g. 'IPL', 'Modi')"}},
            "required": ["keyword"],
        },
    },
    {
        "name": "get_news_articles",
        "description": "Retrieve fetched news articles by topic/keyword name. Pass the topic as a plain string (e.g. 'IPL', 'Trump Modi war'). Optionally narrow results with a free-text query.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "Topic or keyword name to fetch articles for (e.g. 'IPL'). Leave empty for all."},
                "query": {"type": "string", "description": "Optional free-text search within the returned articles"},
                "page": {"type": "integer", "default": 1},
                "limit": {"type": "integer", "default": 10, "description": "Articles per page (1–100)"},
            },
        },
    },
    {
        "name": "suggest_news_keyword",
        "description": "Use the LLM to suggest an optimised news search term from a natural-language topic.",
        "inputSchema": {
            "type": "object",
            "properties": {"topic": {"type": "string", "description": "Natural language topic or subject to monitor"}},
            "required": ["topic"],
        },
    },
]

# ── News handlers ──────────────────────────────────────────────────────────────

async def _handle_list_news_keywords(args: Dict[str, Any]) -> str:
    if _news_service is None:
        return "News service not available (set news.enabled=true in config)."
    try:
        keywords = _news_service.list_keywords()
        if not keywords:
            return "No keywords tracked yet. Use create_news_keyword to add one."
        lines = []
        for kw in keywords:
            status = "active" if kw.enabled else "paused"
            last = kw.last_fetched_at.isoformat() if kw.last_fetched_at else "never"
            lines.append(
                f"- [{status}] \"{kw.term}\" (id={kw.id}) | "
                f"interval={kw.fetch_interval_minutes}min | articles={kw.article_count} | last={last}"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {e}"


async def _handle_create_news_keyword(args: Dict[str, Any]) -> str:
    if _news_service is None:
        return "News service not available."
    try:
        from ..news.models import KeywordCreate
        req = KeywordCreate(
            term=args["term"],
            fetch_interval_minutes=int(args.get("fetch_interval_minutes", 60)),
            max_articles_per_fetch=int(args.get("max_articles_per_fetch", 10)),
        )
        if _news_service.keyword_exists(req.term):
            return f"Keyword \"{req.term}\" already exists."
        kw = _news_service.create_keyword(req)
        return f"Created: \"{kw.term}\" (id={kw.id}) — fetching every {kw.fetch_interval_minutes}min."
    except Exception as e:
        return f"Error: {e}"


async def _handle_update_news_keyword(args: Dict[str, Any]) -> str:
    if _news_service is None:
        return "News service not available."
    try:
        from ..news.models import KeywordUpdate
        patch = KeywordUpdate(
            term=args.get("term"),
            fetch_interval_minutes=args.get("fetch_interval_minutes"),
            max_articles_per_fetch=args.get("max_articles_per_fetch"),
            enabled=args.get("enabled"),
        )
        kw = _news_service.update_keyword(args["keyword_id"], patch)
        if kw is None:
            return f"Keyword id={args['keyword_id']} not found."
        status = "active" if kw.enabled else "paused"
        return f"Updated: \"{kw.term}\" | interval={kw.fetch_interval_minutes}min | status={status}"
    except Exception as e:
        return f"Error: {e}"


async def _handle_delete_news_keyword(args: Dict[str, Any]) -> str:
    if _news_service is None:
        return "News service not available."
    try:
        ok = _news_service.delete_keyword(args["keyword_id"])
        if not ok:
            return f"Keyword id={args['keyword_id']} not found."
        return f"Keyword id={args['keyword_id']} deleted."
    except Exception as e:
        return f"Error: {e}"


def _resolve_keyword_id(term: str) -> Optional[str]:
    """Resolve a human keyword term to its stored UUID.

    Strategy:
      1. Exact match (case-insensitive)
      2. Substring match (keyword.term contains term, or vice-versa)
      3. LLM-assisted fuzzy pick from the list of known terms
    Returns the keyword UUID or None.
    """
    if _news_service is None:
        return None
    keywords = _news_service.list_keywords()
    if not keywords:
        return None
    term_lower = term.strip().lower()

    # 1. Exact match
    for kw in keywords:
        if kw.term.lower() == term_lower:
            return kw.id

    # 2. Substring match
    for kw in keywords:
        if term_lower in kw.term.lower() or kw.term.lower() in term_lower:
            return kw.id

    # 3. LLM fuzzy pick
    if _orchestrator is not None:
        try:
            known = ", ".join(f'"{kw.term}"' for kw in keywords)
            prompt = (
                f"From this list of tracked news keywords: [{known}], "
                f"which one best matches the user's request: \"{term}\"? "
                f"Reply with ONLY the exact keyword text, nothing else."
            )
            import asyncio as _asyncio
            loop = _asyncio.get_event_loop()
            answer = loop.run_until_complete(
                loop.run_in_executor(None, lambda: _orchestrator.chat_simple(prompt))
            ) if not _asyncio.get_event_loop().is_running() else None
            # Running inside async context — use synchronous wrapper
            if answer is None:
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                    fut = ex.submit(_orchestrator.chat_simple, prompt)
                    answer = fut.result(timeout=15)
            if answer:
                answer_lower = answer.strip().strip('"').lower()
                for kw in keywords:
                    if kw.term.lower() == answer_lower:
                        return kw.id
        except Exception:
            pass

    return None


async def _handle_fetch_news_now(args: Dict[str, Any]) -> str:
    if _news_service is None:
        return "News service not available."
    term = args.get("keyword") or args.get("keyword_id", "")
    kid = _resolve_keyword_id(term)
    if kid is None:
        known = ", ".join(f'"{kw.term}"' for kw in (_news_service.list_keywords() or []))
        return f"Could not find a keyword matching '{term}'. Tracked keywords: {known or 'none'}."
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, _news_service.fetch_now, kid)
    return f"Fetch enqueued for '{term}'. Articles will appear shortly."


async def _handle_get_news_articles(args: Dict[str, Any]) -> str:
    if _news_service is None:
        return "News service not available."
    try:
        term = (args.get("keyword") or "").strip()
        keyword_id: Optional[str] = None

        if term:
            keyword_id = _resolve_keyword_id(term)
            if keyword_id is None:
                known = ", ".join(f'"{kw.term}"' for kw in (_news_service.list_keywords() or []))
                return (
                    f"No tracked keyword found matching '{term}'. "
                    f"Tracked keywords: {known or 'none'}. "
                    f"Use create_news_keyword to start tracking it."
                )

        articles = _news_service.get_articles(
            keyword_id=keyword_id,
            page=int(args.get("page", 1)),
            limit=int(args.get("limit", 10)),
        )

        # Optional free-text filter
        query = (args.get("query") or "").strip().lower()
        if query:
            articles = [
                a for a in articles
                if query in (a.title or "").lower()
                or query in (a.summary or a.content or "").lower()
            ]

        if not articles:
            hint = f" for '{term}'" if term else ""
            return (
                f"No articles found{hint}. "
                f"Use fetch_news_now with keyword='{term}' to trigger an immediate fetch."
            )

        label = f"'{term}'" if term else "all keywords"
        parts = [f"Latest news for {label} ({len(articles)} article(s)):\n"]
        for i, a in enumerate(articles, 1):
            pub = a.published_at.isoformat() if a.published_at else "unknown"
            text = (a.summary or a.content or "")[:300]
            if len(a.summary or a.content or "") > 300:
                text += "…"
            parts.append(f"[{i}] {a.title}\n    Source: {a.source} | {pub}\n    {text}\n    {a.url}")
        return "\n\n".join(parts)
    except Exception as e:
        return f"Error: {e}"


async def _handle_suggest_news_keyword(args: Dict[str, Any]) -> str:
    if _news_service is None:
        return "News service not available."
    try:
        loop = asyncio.get_event_loop()
        topic = args.get("topic") or args.get("description", "")
        result = await loop.run_in_executor(None, _news_service.suggest_keyword, topic)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"


# ── Dynamic tool list (built-in + news only — no forwarded MCP-client tools) ───
# NOTE: forwarded MCP-client tools are NOT included here intentionally.
# Including them would cause circular duplication (RAGenie/RAGenie News/...)  
# when the app is registered as its own MCP client.

def get_tools() -> List[Dict[str, Any]]:
    """Return built-in and news tools. External MCP-client tools are NOT forwarded
    through this server to avoid circular duplication."""
    tools = list(TOOLS)

    if _news_service is not None:
        tools.extend(_NEWS_TOOLS)

    return tools


# ── Dispatcher ─────────────────────────────────────────────────────────────────

_BUILTIN_HANDLERS = {
    "search_documents": _handle_search_documents,
    "search_web": _handle_search_web,
    "list_documents": _handle_list_documents,
    "ask_ragenie": _handle_ask_ragenie,
    "execute_task": _handle_execute_task,
    "list_news_keywords": _handle_list_news_keywords,
    "create_news_keyword": _handle_create_news_keyword,
    "update_news_keyword": _handle_update_news_keyword,
    "delete_news_keyword": _handle_delete_news_keyword,
    "fetch_news_now": _handle_fetch_news_now,
    "get_news_articles": _handle_get_news_articles,
    "suggest_news_keyword": _handle_suggest_news_keyword,
}


async def call_tool(name: str, args: Dict[str, Any]) -> str:
    # Built-in handler
    handler = _BUILTIN_HANDLERS.get(name)
    if handler:
        return await handler(args)

    # Forwarded MCP-client tool (format: "ServerName/tool_name")
    if _mcp_client_manager is not None and "/" in name:
        try:
            return await _mcp_client_manager.call_tool(name, args)
        except Exception as e:
            logger.error(f"Forwarded tool '{name}' failed: {e}")
            return f"Error calling forwarded tool '{name}': {e}"

    raise ValueError(f"Unknown tool: '{name}'")
