import asyncio
import contextvars
import json
import re
import warnings
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from langchain.agents import AgentExecutor, create_react_agent
from langchain.prompts import PromptTemplate
from langchain.tools import Tool
from langchain import hub

from ..llm.langchain_wrapper import LangChainLLM
from ..llm.prompts import SYSTEM_PROMPT
from ..rag.page_index_store import PageIndexStore
from ..rag.context_builder import ContextBuilder
from ..search.search_service import SearchService
from ..search.langchain_tool import create_search_tool
from ..core.models import Conversation, Message
from ..core.logging_config import get_logger
from ..core.exceptions import GenerationError
from ..memory.memory_manager import MemoryManager
from ..memory.models import MemoryType
from ..security.input_sanitizer import sanitize_user_input
from ..security.document_filter import filter_document_chunk
from ..security.prompt_builder import build_secure_prompt

if TYPE_CHECKING:
    from ..mcp_client.manager import MCPClientManager
    from ..mcp_client.multi_user_manager import MultiUserMCPManagerRegistry

logger = get_logger(__name__)

_REACT_PROMPT_CACHE = None  # pulled once; reused on every rebuild_tools

# Per-request user_id, set at the start of achat()/chat()/chat_simple().
# Read by tool closures (e.g. news tools) that are built once but must act on
# behalf of whichever user's request is currently executing. Safe under asyncio
# concurrency because ContextVars are isolated per task.
_current_user_id: "contextvars.ContextVar[str]" = contextvars.ContextVar(
    "_current_user_id", default=""
)


class ChatOrchestrator:
    """Orchestrate chat interactions with RAG and search capabilities."""
    
    def __init__(
        self,
        llm_wrapper: LangChainLLM,
        rag_store: PageIndexStore,
        search_service: SearchService,
        max_history: int = 10,
        memory_manager: Optional[MemoryManager] = None,
        mcp_client_manager: Optional["MCPClientManager"] = None,
        mcp_manager_registry: Optional["MultiUserMCPManagerRegistry"] = None,
        news_service: Optional[Any] = None,
    ):
        self.llm_wrapper = llm_wrapper
        self.rag_store = rag_store
        self.search_service = search_service
        self.context_builder = ContextBuilder()
        self.max_history = max_history
        self.conversation: Optional[Conversation] = None
        self.memory_manager: Optional[MemoryManager] = memory_manager
        # Legacy single-manager mode (backward-compat, e.g. simple/no-auth setups).
        self._mcp_client_manager: Optional["MCPClientManager"] = mcp_client_manager
        # Multi-user mode: resolves a per-user MCPClientManager at request time so
        # one user's connected servers/tools are never visible to another user.
        self._mcp_manager_registry: Optional["MultiUserMCPManagerRegistry"] = mcp_manager_registry
        self._news_service: Optional[Any] = news_service
        
        # Create tools
        self.tools = self._create_tools()
        
        # Create agent
        self.agent = self._create_agent()

    def _build_mcp_tools(self, mgr: "MCPClientManager") -> List[Tool]:
        """Build LangChain Tool objects from a given MCPClientManager's tool registry."""
        tools: List[Tool] = []
        for td in mgr.list_all_tools():
            llm_name = f"{td.server_name}/{td.name}"
            description = f"[MCP:{td.server_name}] {td.description}"
            manager_ref = mgr

            async def _mcp_coroutine(args_str: str, _llm_name: str = llm_name, _mgr=manager_ref) -> str:
                try:
                    try:
                        parsed = json.loads(args_str)
                    except (json.JSONDecodeError, TypeError):
                        parsed = {"input": str(args_str)}
                    result = await _mgr.call_tool(_llm_name, parsed)
                    self._log_mcp_tool_call(_llm_name)
                    return result
                except Exception as e:
                    return f"Error calling MCP tool '{_llm_name}': {e}"

            def _mcp_sync(args_str: str, _coro=_mcp_coroutine) -> str:
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as pool:
                            future = pool.submit(asyncio.run, _coro(args_str))
                            return future.result(timeout=35)
                    return loop.run_until_complete(_coro(args_str))
                except Exception as e:
                    return f"Error: {e}"

            tools.append(Tool(
                name=llm_name,
                description=description,
                func=_mcp_sync,
                coroutine=_mcp_coroutine,
            ))
        return tools

    @staticmethod
    def _log_mcp_tool_call(tool_name: str) -> None:
        """Best-effort activity logging for MCP tool calls made by the agent."""
        user_id = _current_user_id.get()
        if not user_id:
            return
        try:
            from ..api.app import app_state
            activity_logger = app_state.get("activity_logger")
            if activity_logger:
                activity_logger.log(user_id, "mcp_tool_call", f"Agent called MCP tool '{tool_name}'", {"tool": tool_name})
        except Exception:
            pass

    async def _get_dynamic_mcp_tools(self, user_id: Optional[str]) -> List[Tool]:
        """Resolve the requesting user's own MCP tools (multi-user mode only)."""
        if self._mcp_manager_registry is None or not user_id:
            return []
        try:
            mgr = await self._mcp_manager_registry.get_or_create(user_id)
            return self._build_mcp_tools(mgr)
        except Exception as e:
            logger.warning(f"Could not resolve MCP tools for user {user_id}: {e}")
            return []

    def _create_tools(self) -> List[Tool]:
        """Create LangChain tools for the agent (built-in + legacy static MCP)."""
        tools = []
        
        # RAG search tool
        def rag_search(query: str) -> str:
            """Search the knowledge base for relevant information."""
            try:
                chunks = self.rag_store.search_chunks(query, top_k=5, user_id=_current_user_id.get() or None)
                if not chunks:
                    return "No relevant information found in the knowledge base."
                
                context = self.context_builder.build_context(chunks)
                return f"Knowledge base results:\n{context}"
            except Exception as e:
                logger.error(f"RAG search error: {str(e)}")
                return f"Error searching knowledge base: {str(e)}"
        
        rag_tool = Tool(
            name="knowledge_base_search",
            description="Search the local knowledge base for information from ingested documents. Use this for questions about stored documents or specific domain knowledge.",
            func=rag_search
        )
        tools.append(rag_tool)
        
        # Web search tool
        search_tool = create_search_tool(self.search_service)
        tools.append(search_tool)

        # Legacy single-manager MCP tools (only used when no per-user registry is configured)
        if self._mcp_client_manager and self._mcp_manager_registry is None:
            for td in self._mcp_client_manager.list_all_tools():
                llm_name = f"{td.server_name}/{td.name}"
                description = f"[MCP:{td.server_name}] {td.description}"
                manager_ref = self._mcp_client_manager

                async def _mcp_coroutine(args_str: str, _llm_name: str = llm_name, _mgr=manager_ref) -> str:
                    try:
                        try:
                            parsed = json.loads(args_str)
                        except (json.JSONDecodeError, TypeError):
                            parsed = {"input": str(args_str)}
                        return await _mgr.call_tool(_llm_name, parsed)
                    except Exception as e:
                        return f"Error calling MCP tool '{_llm_name}': {e}"

                def _mcp_sync(args_str: str, _coro=_mcp_coroutine) -> str:
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            import concurrent.futures
                            with concurrent.futures.ThreadPoolExecutor() as pool:
                                future = pool.submit(asyncio.run, _coro(args_str))
                                return future.result(timeout=35)
                        return loop.run_until_complete(_coro(args_str))
                    except Exception as e:
                        return f"Error: {e}"

                tool = Tool(
                    name=llm_name,
                    description=description,
                    func=_mcp_sync,
                    coroutine=_mcp_coroutine,
                )
                tools.append(tool)

        # News tools (populated after news service starts via set_news_service())
        tools.extend(self._create_news_tools())

        return tools

    def _create_news_tools(self) -> List[Tool]:
        """Create LangChain tools for news keyword management."""
        if self._news_service is None:
            return []

        svc = self._news_service

        def _parse(args_str: str, default_key: str = "term") -> dict:
            s = args_str.strip()
            if s.startswith("{"):
                try:
                    return json.loads(s)
                except Exception:
                    pass
            return {default_key: s}

        def _resolve_kw_id(term: str):
            term_l = term.strip().lower()
            for kw in (svc.list_keywords(_current_user_id.get()) or []):
                if kw.term.lower() == term_l or term_l in kw.term.lower() or kw.term.lower() in term_l:
                    return kw.id, kw.term
            return None, None

        def _create_kw(args_str: str) -> str:
            try:
                uid = _current_user_id.get()
                parsed = _parse(args_str)
                term = parsed.get("term", args_str).strip()
                interval = int(parsed.get("fetch_interval_minutes", 60))
                max_art  = int(parsed.get("max_articles_per_fetch", 10))
                if not term:
                    return "Error: topic name (term) is required."
                if svc.keyword_exists(uid, term):
                    return f'News keyword "{term}" is already being tracked.'
                from ..news.models import KeywordCreate
                kw = svc.create_keyword(uid, KeywordCreate(
                    term=term,
                    fetch_interval_minutes=interval,
                    max_articles_per_fetch=max_art,
                ))
                return (
                    f'Done! Created news keyword "{kw.term}" — '
                    f'fetching every {kw.fetch_interval_minutes} min, '
                    f'up to {kw.max_articles_per_fetch} articles per cycle. '
                    f'Articles will appear in the News tab shortly.'
                )
            except Exception as e:
                return f"Error creating news keyword: {e}"

        def _list_kw(args_str: str) -> str:
            try:
                keywords = svc.list_keywords(_current_user_id.get())
                if not keywords:
                    return "No news topics tracked yet. Ask me to create one."
                lines = []
                for kw in keywords:
                    status = "active" if kw.enabled else "paused"
                    last   = kw.last_fetched_at.isoformat() if kw.last_fetched_at else "never"
                    lines.append(
                        f'- "{kw.term}" [{status}] | every {kw.fetch_interval_minutes}min '
                        f'| {kw.article_count} articles | last fetched: {last}'
                    )
                return "Tracked news keywords:\n" + "\n".join(lines)
            except Exception as e:
                return f"Error: {e}"

        def _get_articles(args_str: str) -> str:
            try:
                parsed  = _parse(args_str, "keyword")
                term    = parsed.get("keyword", args_str).strip()
                kw_id, kw_term = _resolve_kw_id(term)
                articles = svc.get_articles(keyword_id=kw_id, page=1, limit=5)
                if not articles:
                    return f'No articles yet for "{term}". Try asking me to fetch news now.'
                parts = [f'Latest news for "{kw_term or term}" ({len(articles)} articles):']
                for i, a in enumerate(articles, 1):
                    summary = (a.summary or a.content or "")[:200]
                    parts.append(f'[{i}] {a.title}\n    {summary}')
                return "\n\n".join(parts)
            except Exception as e:
                return f"Error: {e}"

        def _fetch_now(args_str: str) -> str:
            try:
                parsed = _parse(args_str, "keyword")
                term   = parsed.get("keyword", args_str).strip()
                kw_id, kw_term = _resolve_kw_id(term)
                if kw_id is None:
                    known = ", ".join(f'"{k.term}"' for k in (svc.list_keywords(_current_user_id.get()) or []))
                    return f'No keyword matching "{term}". Tracked: {known or "none"}.'
                import threading
                threading.Thread(target=svc.fetch_now, args=(kw_id,), daemon=True).start()
                return f'Fetching latest news for "{kw_term}" now. Check the News tab in a moment.'
            except Exception as e:
                return f"Error: {e}"

        return [
            Tool(
                name="create_news_keyword",
                description=(
                    "Create a news topic/keyword to track in the news feed. "
                    "Use this when the user asks to monitor, track, or follow news on a topic. "
                    'Input JSON: {"term": "IPL", "fetch_interval_minutes": 15, "max_articles_per_fetch": 10} '
                    "or just the topic name as plain text. Default interval is 60 minutes."
                ),
                func=_create_kw,
            ),
            Tool(
                name="list_news_keywords",
                description="List all news topics/keywords currently being tracked. No input needed.",
                func=_list_kw,
            ),
            Tool(
                name="get_news_articles",
                description=(
                    "Get the most recent news articles for a tracked topic. "
                    "Input: topic name (e.g. 'IPL') or JSON {\"keyword\": \"IPL\"}."
                ),
                func=_get_articles,
            ),
            Tool(
                name="fetch_news_now",
                description=(
                    "Immediately fetch the latest news for a tracked topic without waiting for the schedule. "
                    "Input: topic name."
                ),
                func=_fetch_now,
            ),
        ]

    def set_news_service(self, news_service: Any) -> None:
        """Inject news service after startup and rebuild agent tools."""
        self._news_service = news_service
        self.rebuild_tools()
        logger.info("Orchestrator: news tools added to agent")

    # ── Tool selection ────────────────────────────────────────────────────────

    _NEWS_HINTS = (
        "news keyword", "track news", "follow news", "monitor news",
        "create keyword", "add keyword", "news topic", "fetch news",
        "news articles", "get news", "latest news", "news on",
        # STT-error variants (e.g. "keyword" → "speed", "create" → "written")
        "news feed", "news for", "news about", "speed on", "feed for",
        "new speed", "set up news", "start news",
    )
    _NEWS_TOOL_NAMES = {
        "create_news_keyword", "list_news_keywords",
        "get_news_articles", "fetch_news_now",
        # MCP-backed variants
        "RAGenie News/create_news_keyword", "RAGenie News/list_news_keywords",
        "RAGenie News/get_news_articles",  "RAGenie News/fetch_news_now",
        "RAGenie/create_news_keyword",     "RAGenie/list_news_keywords",
        "RAGenie/get_news_articles",       "RAGenie/fetch_news_now",
    }
    _DOC_HINTS = (
        "document", "file", "pdf", "upload", "indexed", "knowledge base",
    )
    _MAX_GENERAL_TOOLS = 12

    def _select_tools_for_query(self, message: str, tools: Optional[List[Tool]] = None) -> List[Tool]:
        """Return a focused subset of tools relevant to the user's query.

        Small LLMs (llama3.2 ~2 GB) hallucinate when given 40+ tools.
        Narrowing to the most relevant set dramatically improves reliability.

        `tools` defaults to `self.tools` but callers in multi-user mode pass an
        explicit pool that includes the requesting user's own dynamic MCP tools.
        """
        pool = tools if tools is not None else self.tools
        msg = message.lower()

        # ── News keyword management ──────────────────────────────────────────
        if any(h in msg for h in self._NEWS_HINTS):
            selected = [t for t in pool if t.name in self._NEWS_TOOL_NAMES]
            if selected:
                logger.info(f"Tool filter: news intent detected — {[t.name for t in selected]}")
                return selected

        # ── Document / RAG queries ───────────────────────────────────────────
        if any(h in msg for h in self._DOC_HINTS):
            selected = [t for t in pool if t.name in (
                "knowledge_base_search", "web_search",
                "RAGenie/search_documents", "RAGenie/list_documents",
            )]
            if selected:
                logger.info(f"Tool filter: document intent — {[t.name for t in selected]}")
                return selected

        # ── General query: cap at _MAX_GENERAL_TOOLS, rank by keyword overlap ─
        if len(pool) <= self._MAX_GENERAL_TOOLS:
            return pool
        msg_words = set(msg.split())
        def _score(tool):
            hay = f"{tool.name} {tool.description or ''}".lower()
            return sum(1 for w in msg_words if len(w) > 3 and w in hay)
        ranked = sorted(pool, key=_score, reverse=True)
        top = ranked[:self._MAX_GENERAL_TOOLS]
        logger.info(f"Tool filter: general — top {len(top)}: {[t.name for t in top[:5]]}...")
        return top

    # ── Direct command executor (bypasses LLM for reliable CRUD) ──────────

    def _try_direct_command(self, message: str) -> Optional[str]:
        """Execute known voice commands directly without LLM involvement.

        Returns the response string if handled, or None to fall through to the agent.
        Handles speech-recognition imperfections (mishearing, extra words).
        """
        if self._news_service is None:
            return None

        msg = message.strip()
        msg_l = msg.lower()

        # ── List tracked keywords ────────────────────────────────────────────
        if re.search(
            r'(?:list|show|what).{0,30}(?:news keyword|track|follow|monitor)',
            msg_l,
        ):
            try:
                kws = self._news_service.list_keywords(_current_user_id.get())
                if not kws:
                    return "You have no news keywords tracked yet. Say 'create a news keyword for [topic]' to start."
                lines = [f'"{k.term}" — every {k.fetch_interval_minutes} min, {k.article_count} articles' for k in kws]
                return "Tracked news topics: " + "; ".join(lines) + "."
            except Exception as e:
                logger.error(f"Direct list_keywords failed: {e}")
                return None

        # ── News keyword creation ────────────────────────────────────────────
        # Detect intent: any phrasing that implies CREATE + NEWS KEYWORD
        # Also catches STT variants: "news feed", "new speed", "written news feed"
        create_intent = bool(re.search(
            r'(?:creat|add|start|track|monitor|follow|set up|written).{0,60}'
            r'(?:news.{0,15}(?:keyword|topic|feed|speed)|(?:keyword|topic).{0,15}news)',
            msg_l,
        ))

        # "news feed for TOPIC" / "news on TOPIC" alone implies creation intent
        if not create_intent:
            create_intent = bool(re.search(
                r'\bnews\s+(?:feed|on|for|about)\b', msg_l
            ))

        # STT mishears "news keyword" as "new skew word", "new key word", etc.
        # Catch "new(s)? <any word(s)> word/term for <topic>"
        if not create_intent:
            create_intent = bool(re.search(
                r'\bnew(?:s)?\b.{0,30}\b(?:word|term|keyword|kw)\b', msg_l
            ))

        if not create_intent:
            return None

        # ── Extract topic ────────────────────────────────────────────────────
        topic: Optional[str] = None

        # Try: "keyword for/on/about TOPIC [every|and|fetch]"
        m = re.search(
            r'\b(?:keyword|topic)\s+(?:for|on|about|named|called)?\s*([A-Za-z0-9][A-Za-z0-9 ]{1,40}?)'
            r'(?=\s+(?:every|and|fetch|in|,|\.|$))',
            msg, re.IGNORECASE,
        )
        if m:
            topic = m.group(1).strip()

        if not topic:
            # Try: "news on/for/about TOPIC"
            m = re.search(
                r'\bnews\s+(?:on|for|about|regarding)\s+([A-Za-z0-9][A-Za-z0-9 ]{1,40}?)'
                r'(?=\s+(?:every|and|fetch|,|\.|$))',
                msg, re.IGNORECASE,
            )
            if m:
                topic = m.group(1).strip()

        if not topic:
            # Fallback: word(s) after "for"/"on" before "every"/"and" or end-of-string
            m = re.search(
                r'\b(?:for|on)\s+([A-Za-z0-9][A-Za-z0-9 ]{0,30}?)'
                r'(?=\s*(?:every|and|fetch|,|[.!?]|$))',
                msg, re.IGNORECASE,
            )
            if m:
                topic = m.group(1).strip()

        if not topic:
            # Final fallback: last word(s) after a preposition at end of utterance
            # Handles "create a new speed on NASA." and similar STT output
            m = re.search(
                r'\b(?:for|on|about|of|regarding)\s+'
                r'([A-Za-z][A-Za-z0-9 ]{0,39}?)\s*[.!?,]?\s*$',
                msg, re.IGNORECASE,
            )
            if m:
                topic = m.group(1).strip()

        if not topic:
            return None  # can't determine topic — let agent handle it

        # Strip stray trailing words like "and", "the"
        topic = re.sub(r'\s+(?:and|the|a|an)$', '', topic, flags=re.IGNORECASE).strip()

        # ── Extract interval ─────────────────────────────────────────────────
        interval = 60  # default
        m = re.search(r'every\s+(\d+)\s*(?:min(?:utes?)?|mins?)', msg_l)
        if m:
            interval = int(m.group(1))

        # ── Create keyword ───────────────────────────────────────────────────
        try:
            uid = _current_user_id.get()
            if self._news_service.keyword_exists(uid, topic):
                return (
                    f'I\'m already tracking news on "{topic}". '
                    f'You can ask me for the latest articles any time.'
                )
            from ..news.models import KeywordCreate
            kw = self._news_service.create_keyword(uid, KeywordCreate(
                term=topic,
                fetch_interval_minutes=interval,
                max_articles_per_fetch=10,
            ))
            logger.info(f"Direct command: created news keyword '{kw.term}' every {kw.fetch_interval_minutes}min")
            return (
                f'Done! I\'ve started tracking news on "{kw.term}" — '
                f'fetching every {kw.fetch_interval_minutes} minutes. '
                f'Check the News tab shortly for articles.'
            )
        except Exception as e:
            logger.error(f"Direct command create_news_keyword failed: {e}")
            return None  # fall through to agent

    @staticmethod
    def _seems_action_claim(text: str) -> bool:
        """Return True when the response CLAIMS an action without proof."""
        t = text.lower()
        action_phrases = (
            "i have created", "i've created", "i created",
            "i have set", "i've set", "i set up",
            "i have added", "i've added", "keyword has been",
            "has been created", "successfully created", "i have tracked",
        )
        return any(p in t for p in action_phrases)

    def rebuild_tools(self) -> None:
        """Rebuild tool list and agent — called when MCP servers connect/disconnect."""
        self.tools = self._create_tools()
        self.agent = self._create_agent()
        tool_names = [t.name for t in self.tools]
        logger.info(f"Tools rebuilt: {tool_names}")
    
    def _create_agent(self) -> AgentExecutor:
        """Create a LangChain agent with tools."""
        global _REACT_PROMPT_CACHE
        if _REACT_PROMPT_CACHE is not None:
            prompt = _REACT_PROMPT_CACHE
        else:
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", DeprecationWarning)
                    prompt = hub.pull("hwchase17/react")
                _REACT_PROMPT_CACHE = prompt
            except Exception as e:
                logger.warning(f"Could not pull prompt from hub: {e}. Using fallback prompt.")
                template = """Answer the following questions as best you can. You have access to the following tools:

{tools}

Use the following format:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

Begin!

Question: {input}
Thought:{agent_scratchpad}"""
                prompt = PromptTemplate.from_template(template)
                _REACT_PROMPT_CACHE = prompt
        
        llm = self.llm_wrapper.get_llm()
        agent = create_react_agent(llm, self.tools, prompt)
        
        def _react_parse_error_handler(error: Exception) -> str:
            return (
                "Format error — your last response was not valid ReAct format. "
                "You MUST write exactly one of:\n"
                "  Thought: <reasoning>\n  Action: <tool>\n  Action Input: {\"key\": \"value\"}\n"
                "OR\n"
                "  Thought: I now know the final answer\n  Final Answer: <answer>\n"
                "Do NOT write bare text after Thought:. Try again now."
            )

        agent_executor = AgentExecutor(
            agent=agent,
            tools=self.tools,
            verbose=True,
            handle_parsing_errors=_react_parse_error_handler,
            max_iterations=15,
            max_execution_time=180,
            return_intermediate_steps=True,
            early_stopping_method="force",
        )
        
        return agent_executor
    
    def start_conversation(self, conversation_id: str) -> Conversation:
        """Start a new conversation."""
        self.conversation = Conversation(conversation_id=conversation_id)
        logger.info(f"Started conversation: {conversation_id}")
        return self.conversation
    
    def chat(self, user_message: str, user_id: Optional[str] = None) -> str:
        """Process a user message using the LangChain agent (sync)."""
        if self.conversation is None:
            raise ValueError("No active conversation. Call start_conversation() first.")

        _current_user_id.set(user_id or "")
        logger.info(f"Processing message: {user_message}")
        self.conversation.add_message("user", user_message)
        
        _STOP_SENTINEL = "Agent stopped due to iteration limit or time limit"
        try:
            response = self.agent.invoke({"input": user_message})
            raw_output = response.get("output", "")
            if _STOP_SENTINEL in raw_output:
                steps = response.get("intermediate_steps", [])
                if steps:
                    last_obs = str(steps[-1][1]) if steps[-1][1] else ""
                    assistant_message = last_obs if last_obs else "I was unable to complete that request within the allowed steps. Please try a simpler or more specific question."
                else:
                    assistant_message = "I was unable to complete that request within the allowed steps. Please try a simpler or more specific question."
                logger.warning(f"Agent hit iteration/time limit for: {user_message[:80]}")
            else:
                assistant_message = raw_output or "I apologize, but I couldn't generate a response."
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            assistant_message = f"I encountered an error: {str(e)}"
        
        self.conversation.add_message("assistant", assistant_message)
        self._prune_history()
        
        logger.info("Response generated successfully")
        return assistant_message

    def _build_executor(self, tools: List[Tool], llm_override=None) -> AgentExecutor:
        """Build a fresh AgentExecutor with the given tool subset."""
        global _REACT_PROMPT_CACHE
        prompt = _REACT_PROMPT_CACHE  # already populated by _create_agent()
        llm = llm_override if llm_override is not None else self.llm_wrapper.get_llm()
        agent = create_react_agent(llm, tools, prompt)

        def _parse_err(e: Exception) -> str:
            return (
                "Format error — your last response was not valid ReAct format. "
                "You MUST write exactly one of:\n"
                "  Thought: <reasoning>\n  Action: <tool>\n  Action Input: {\"key\": \"value\"}\n"
                "OR\n"
                "  Thought: I now know the final answer\n  Final Answer: <answer>\n"
                "Do NOT write bare text after Thought:. Try again now."
            )

        return AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=True,
            handle_parsing_errors=_parse_err,
            max_iterations=10,
            max_execution_time=120,
            return_intermediate_steps=True,
            early_stopping_method="force",
        )

    async def achat(
        self,
        user_message: str,
        callbacks: Optional[List] = None,
        llm_override=None,
        user_id: Optional[str] = None,
    ) -> str:
        """Async agent mode — supports MCP coroutine tools properly."""
        if self.conversation is None:
            raise ValueError("No active conversation. Call start_conversation() first.")

        _current_user_id.set(user_id or "")
        logger.info(f"Processing agent message (async): {user_message}")
        self.conversation.add_message("user", user_message)

        _STOP_SENTINEL = "Agent stopped due to iteration limit or time limit"

        async def _run(tools: List[Tool], input_text: str) -> dict:
            executor = self._build_executor(tools, llm_override=llm_override)
            cfg = {"callbacks": callbacks} if callbacks else {}
            return await executor.ainvoke({"input": input_text}, config=cfg)

        try:
            # ── Direct command check (no LLM) ────────────────────────────────
            direct = self._try_direct_command(user_message)
            if direct is not None:
                self.conversation.add_message("assistant", direct)
                self._prune_history()
                logger.info("Direct command executed — LLM bypassed")
                return direct

            # First pass: focused tool list for this query (includes this user's own MCP tools)
            dynamic_mcp_tools = await self._get_dynamic_mcp_tools(user_id)
            tool_pool = self.tools + dynamic_mcp_tools if dynamic_mcp_tools else self.tools
            active_tools = self._select_tools_for_query(user_message, tools=tool_pool)
            response = await _run(active_tools, user_message)
            raw_output = response.get("output", "")
            steps = response.get("intermediate_steps", [])

            # ── Hallucination detection ───────────────────────────────────────
            # If the model claimed to do something but called no tools, retry
            # with an explicit forcing instruction so the action is really taken.
            if not steps and self._seems_action_claim(raw_output):
                logger.warning(
                    f"Possible hallucination detected (no tool calls, action claim): "
                    f"{raw_output[:80]!r} — retrying with explicit force"
                )
                forced = (
                    f"{user_message}\n\n"
                    "IMPORTANT: You MUST call the appropriate tool to complete this request. "
                    "Do NOT guess or fabricate a result. "
                    "Write Action: and Action Input: now."
                )
                response = await _run(active_tools, forced)
                raw_output = response.get("output", "")
                steps   = response.get("intermediate_steps", [])

            if _STOP_SENTINEL in raw_output:
                if steps:
                    last_obs = str(steps[-1][1]) if steps[-1][1] else ""
                    assistant_message = last_obs or "I was unable to complete that request. Please try again."
                else:
                    assistant_message = "I was unable to complete that request within the allowed steps. Please try a simpler question."
                logger.warning(f"Agent hit iteration/time limit for: {user_message[:80]}")
            else:
                assistant_message = raw_output or "I apologize, but I couldn't generate a response."
        except Exception as e:
            logger.error(f"Error generating async agent response: {str(e)}")
            assistant_message = f"I encountered an error: {str(e)}"

        self.conversation.add_message("assistant", assistant_message)
        self._prune_history()
        logger.info("Async agent response generated successfully")
        return assistant_message
    
    def chat_simple(self, user_message: str, use_reasoning: bool = False, user_id: Optional[str] = None) -> str:
        """Simple chat without agent (direct LLM call with RAG and memory context)."""
        if self.conversation is None:
            raise ValueError("No active conversation. Call start_conversation() first.")

        _current_user_id.set(user_id or "")

        # --- Security: sanitize user input ---
        sanitized = sanitize_user_input(user_message)
        if sanitized.risk_score >= 0.75:
            logger.warning(
                f"High-risk input detected (score={sanitized.risk_score:.2f}) "
                f"flags={sanitized.flags}"
            )
        user_message = sanitized.text

        logger.info(f"Processing simple message (len={len(user_message)})")
        self.conversation.add_message("user", user_message)
        
        try:
            # Search RAG for context
            raw_chunks = self.rag_store.search_chunks(user_message, top_k=5, user_id=_current_user_id.get() or None)

            # --- Security: filter document chunks ---
            safe_chunks = []
            for chunk in raw_chunks:
                filtered = filter_document_chunk(chunk.content)
                if filtered.blocked:
                    logger.warning(f"Chunk blocked: {filtered.reason}")
                    continue
                chunk.content = filtered.content
                safe_chunks.append(chunk)

            # Build conversation history
            history = self._format_history(exclude_last_user=True)

            # Build memory context
            memory_context = ""
            if self.memory_manager:
                memory_context = self.memory_manager.get_relevant_context(
                    user_message, max_context=1500
                )

            # --- Security: use secure prompt builder ---
            documents = self.context_builder.build_context(safe_chunks) if safe_chunks else ""
            prompt = build_secure_prompt(
                system=SYSTEM_PROMPT,
                user_query=user_message,
                documents=documents,
                history=history,
                memory_context=memory_context,
            )
            
            logger.info(f"Generating response (reasoning: {use_reasoning})")
            response = self.llm_wrapper.generate(prompt, use_reasoning=use_reasoning)
            
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            response = f"I encountered an error: {str(e)}"
        
        self.conversation.add_message("assistant", response)

        # Store conversation in memory
        if self.memory_manager:
            self.memory_manager.store_conversation(user_message, response)

        self._prune_history()
        
        logger.info("Simple response generated successfully")
        return response
    
    def chat_with_reasoning(self, user_message: str) -> Dict[str, str]:
        """Chat with explicit reasoning step (multi-model mode only)."""
        if self.conversation is None:
            raise ValueError("No active conversation. Call start_conversation() first.")

        sanitized = sanitize_user_input(user_message)
        if sanitized.risk_score >= 0.75:
            logger.warning(f"High-risk input (reasoning): score={sanitized.risk_score:.2f}")
        user_message = sanitized.text

        logger.info(f"Processing message with reasoning (len={len(user_message)})")
        self.conversation.add_message("user", user_message)
        
        try:
            raw_chunks = self.rag_store.search_chunks(user_message, top_k=5, user_id=_current_user_id.get() or None)
            safe_chunks = []
            for chunk in raw_chunks:
                filtered = filter_document_chunk(chunk.content)
                if not filtered.blocked:
                    chunk.content = filtered.content
                    safe_chunks.append(chunk)
            history = self._format_history(exclude_last_user=True)
            documents = self.context_builder.build_context(safe_chunks) if safe_chunks else ""
            prompt = build_secure_prompt(
                system=SYSTEM_PROMPT,
                user_query=user_message,
                documents=documents,
                history=history,
            )
            
            reasoning, response = self.llm_wrapper.generate_with_reasoning(prompt)
            result = {"reasoning": reasoning, "response": response}
            
        except Exception as e:
            logger.error(f"Error generating response with reasoning: {str(e)}")
            result = {"reasoning": "", "response": f"I encountered an error: {str(e)}"}
        
        self.conversation.add_message("assistant", result["response"])
        self._prune_history()
        
        logger.info("Response with reasoning generated successfully")
        return result
    
    def _format_history(self, exclude_last_user: bool = True, max_chars_per_msg: int = 500) -> str:
        """Format conversation history as a chat transcript for the LLM."""
        if self.conversation is None or not self.conversation.messages:
            return ""
        
        messages = list(self.conversation.messages)
        if exclude_last_user and messages and messages[-1].role == "user":
            messages = messages[:-1]
        
        if not messages:
            return ""
        
        lines = []
        for msg in messages:
            role_label = "User" if msg.role == "user" else "Assistant"
            content = msg.content
            if len(content) > max_chars_per_msg:
                content = content[:max_chars_per_msg] + "..."
            lines.append(f"{role_label}: {content}")
        
        return "\n".join(lines)

    def _prune_history(self):
        """Prune conversation history to max_history messages."""
        if len(self.conversation.messages) > self.max_history:
            self.conversation.messages = self.conversation.messages[-self.max_history:]
            logger.debug(f"Pruned conversation history to {self.max_history} messages")
    
    def get_conversation_history(self) -> List[Dict[str, Any]]:
        """Get the conversation history."""
        if self.conversation is None:
            return []
        
        return [
            {
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat()
            }
            for msg in self.conversation.messages
        ]
    
    def clear_conversation(self):
        """Clear the current conversation."""
        if self.conversation:
            conversation_id = self.conversation.conversation_id
            self.conversation = Conversation(conversation_id=conversation_id)
            logger.info("Conversation cleared")
