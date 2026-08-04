"""REST API for MCP client server management.

IMPORTANT: Static routes (/import, /export, /chat) are registered BEFORE /{id}
routes to avoid FastAPI matching those words as a server ID.
"""
import json
import re
import time
from typing import Dict, List
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from langchain.agents import AgentExecutor, create_react_agent
from langchain.prompts import PromptTemplate
from langchain.tools import Tool

from ..auth.dependencies import require_auth
from ..auth.models import User
from ..core.logging_config import get_logger
from ..mcp_client import (
    ImportRequest,
    ImportResult,
    MCPChatMessage,
    MCPChatRequest,
    MCPChatResponse,
    MCPClientManager,
    ServerConfig,
    ServerConfigCreate,
    ServerConfigPatch,
    ServerCreateRequest,
    ServerStatus,
    ServerWithStatus,
    TestResult,
    ToolCallTrace,
    ToolDefinition,
)
from ..mcp_client.client import MCPClientConnection
from ..mcp_client.exceptions import MCPConnectionError
from ..mcp_client.models import ConnectionStatus
from ..mcp_client.server_store import ServerConfigStore

# In-memory MCP chat conversation histories  {conv_id: [MCPChatMessage, ...]}
_mcp_chat_histories: Dict[str, List[MCPChatMessage]] = {}

# ── Security constants ───────────────────────────────────────────────────────
# Tools that perform irreversible real-world actions (trades, mutations).
# The LLM may NOT call these autonomously — the user must explicitly request
# them AND include the exact confirmation token in their message.
_DESTRUCTIVE_TOOLS: set = {
    "KITE/place_order", "KITE/modify_order", "KITE/cancel_order",
    "KITE/place_gtt_order", "KITE/modify_gtt_order", "KITE/delete_gtt_order",
}
_CONFIRM_TOKEN = "CONFIRM_TRADE"  # user must include this literal string

# Disallowed URL schemes/hosts to prevent SSRF when adding MCP servers.
# Loopback addresses (localhost / 127.x / ::1) are intentionally ALLOWED so
# users can connect to the app's own built-in MCP SSE server and other local
# development servers.  Cloud metadata endpoints and RFC-1918 private ranges
# remain blocked to prevent network-level SSRF against internal infrastructure.
_SSRF_BLOCKED_HOSTS: set = {
    "169.254.169.254",  # AWS/Azure/GCP instance metadata
    "metadata.google.internal",
}
_SSRF_BLOCKED_SCHEMES: set = {"file", "ftp", "gopher", "dict"}

logger = get_logger(__name__)

router = APIRouter(
    prefix="/mcp-servers",
    tags=["mcp-client"],
)


async def _get_manager(user_id: str) -> MCPClientManager:
    from .app import app_state
    registry = app_state.get("mcp_manager_registry")
    if registry is None:
        raise HTTPException(status_code=503, detail="MCP client manager not initialised")
    return await registry.get_or_create(user_id)


def _log_activity(user_id: str, event_type: str, description: str, metadata: dict = None) -> None:
    from .app import app_state
    activity_logger = app_state.get("activity_logger")
    if activity_logger:
        activity_logger.log(user_id, event_type, description, metadata)


def _owned_or_404(store: "ServerConfigStore", server_id: str, user_id: str) -> "ServerConfig":
    config = store.get(server_id)
    if config is None or config.user_id != user_id:
        raise HTTPException(status_code=404, detail=f"Server not found: {server_id}")
    return config


def _validate_url_for_ssrf(url: str) -> None:
    """Raise 400 if url uses a blocked scheme or points to an internal host."""
    try:
        parsed = urlparse(url)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid URL")
    if parsed.scheme.lower() in _SSRF_BLOCKED_SCHEMES:
        raise HTTPException(status_code=400, detail=f"URL scheme '{parsed.scheme}' is not permitted")
    host = (parsed.hostname or "").lower().rstrip(".")
    if host in _SSRF_BLOCKED_HOSTS:
        raise HTTPException(status_code=400, detail="URL points to a blocked internal host")
    # Block RFC-1918 ranges heuristically (simple string check)
    _RFC1918 = ("10.", "192.168.", "172.16.", "172.17.", "172.18.", "172.19.",
                "172.20.", "172.21.", "172.22.", "172.23.", "172.24.", "172.25.",
                "172.26.", "172.27.", "172.28.", "172.29.", "172.30.", "172.31.")
    if any(host.startswith(p) for p in _RFC1918):
        raise HTTPException(status_code=400, detail="URL points to a private network address")


def _sanitize_tool_result(result: str, tool_name: str, max_chars: int = 500) -> str:
    """Strip prompt-injection patterns and truncate tool results before feeding
    back to the LLM or returning to the frontend."""
    # Login tools must return their full result (URL can be long); raise limit
    if tool_name.endswith("/login"):
        max_chars = 2000
    # Remove instruction-like patterns injected by malicious tool responses.
    # Patterns are intentionally narrow to avoid redacting legitimate content.
    _INJECT_PATTERNS = [
        r"(?i)ignore\s+(all\s+)?previous\s+instructions?",
        r"(?i)you\s+are\s+now\s+(a|an|the)\s+",   # "you are now a different agent"
        r"(?i)new\s+system\s+prompt\s*:",
        r"(?i)disregard\s+(your|all)\s+(previous|prior)\s+",
        r"(?i)pretend\s+(you\s+are|to\s+be)\s+",
    ]
    cleaned = result
    for pat in _INJECT_PATTERNS:
        cleaned = re.sub(pat, "[REDACTED]", cleaned)
    return cleaned[:max_chars]


def _get_store() -> ServerConfigStore:
    from .app import app_state
    store = app_state.get("mcp_client_store")
    if store is None:
        raise HTTPException(status_code=503, detail="MCP client store not initialised")
    return store


# ── Static routes FIRST (before /{id}) ──────────────────────────────────────

@router.get("", response_model=List[ServerWithStatus])
async def list_servers(current_user: User = Depends(require_auth)):
    """List all configured servers with current status and tool counts."""
    mgr = await _get_manager(current_user.id)
    results = mgr.list_servers_with_status()
    for item in results:
        item.config.env = None
        item.config.headers = None
    return results


@router.post("", response_model=ServerWithStatus, status_code=201)
async def create_server(body: ServerCreateRequest, current_user: User = Depends(require_auth)):
    """Create a new MCP server config and optionally connect."""
    store = _get_store()
    mgr = await _get_manager(current_user.id)

    if body.transport == "stdio" and not body.command:
        raise HTTPException(status_code=400, detail="command is required for stdio transport")
    if body.transport in ("sse", "http") and not body.url:
        raise HTTPException(status_code=400, detail="url is required for sse/http transport")

    # SSRF guard: reject private/loopback addresses and dangerous schemes
    if body.url:
        _validate_url_for_ssrf(body.url)

    try:
        create_data = ServerConfigCreate(
            name=body.name,
            transport=body.transport,
            enabled=body.enabled,
            command=body.command,
            args=body.args,
            env=body.env,
            url=body.url,
            headers=body.headers,
        )
        config = store.create(current_user.id, create_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if body.connect_now and config.enabled:
        try:
            await mgr.connect_server(config)
        except MCPConnectionError as e:
            logger.warning(f"Auto-connect failed for '{config.name}': {e}")

    _log_activity(current_user.id, "mcp_server_created", f"Created MCP server '{config.name}'", {"server_id": config.id})

    status = mgr.get_server_status(config.id) or ServerStatus(
        server_id=config.id, status=ConnectionStatus.DISCONNECTED
    )
    tools = []
    conn_map = mgr._connections
    if config.id in conn_map:
        tools = conn_map[config.id].get_tools()

    return ServerWithStatus(config=config, status=status, tools=tools)


@router.post("/import", response_model=ImportResult)
async def import_servers(body: ImportRequest, current_user: User = Depends(require_auth)):
    """Import MCP server configs from Claude Desktop JSON format."""
    store = _get_store()
    mgr = await _get_manager(current_user.id)
    created = updated = skipped = 0

    for name, entry in body.mcpServers.items():
        transport = entry.get("transport", "stdio")
        command = entry.get("command")
        args = entry.get("args")
        env = entry.get("env") or None
        url = entry.get("url")

        if env == {}:
            env = None

        existing = store.get_by_name(current_user.id, name)
        try:
            if existing:
                from ..mcp_client.models import ServerConfigPatch
                patch = ServerConfigPatch(
                    transport=transport,
                    command=command,
                    args=args,
                    env=env,
                    url=url,
                )
                config = store.update(existing.id, patch)
                updated += 1
                if body.connect_now and config.enabled:
                    await mgr.reload_server(config.id)
            else:
                create_data = ServerConfigCreate(
                    name=name,
                    transport=transport,
                    command=command,
                    args=args,
                    env=env,
                    url=url,
                )
                config = store.create(current_user.id, create_data)
                created += 1
                if body.connect_now and config.enabled:
                    try:
                        await mgr.connect_server(config)
                    except MCPConnectionError as e:
                        logger.warning(f"Auto-connect failed for '{name}': {e}")
        except Exception as e:
            logger.error(f"Import failed for '{name}': {e}")
            skipped += 1

    return ImportResult(created=created, updated=updated, skipped=skipped)


@router.get("/export")
async def export_servers(current_user: User = Depends(require_auth)):
    """Export all server configs in Claude Desktop JSON format.
    NOTE: env vars are redacted — they contain credentials."""
    store = _get_store()
    mcp_servers = {}
    for config in store.list(current_user.id):
        entry: dict = {}
        if config.transport == "stdio":
            entry["command"] = config.command or ""
            entry["args"] = config.args or []
            # Redact values but preserve key names so the user knows what to re-fill
            entry["env"] = {k: "***REDACTED***" for k in (config.env or {})}
        else:
            entry["url"] = config.url or ""
            entry["transport"] = config.transport
            # Redact auth headers
            entry["headers"] = {k: "***REDACTED***" for k in (config.headers or {})}
        mcp_servers[config.name] = entry
    return {"mcpServers": mcp_servers}


# ── MCP agent-chat ────────────────────────────────────────────────────────────

_REACT_TEMPLATE = """You are a MANDATORY tool-calling agent. You have real, working tools listed below.
Your ONLY job is to call tools and report what they return.

CRITICAL: You are NOT a chatbot. You cannot answer from memory. You MUST call a tool first.
FORBIDDEN phrases — writing any of these ends the task as a failure:
  "I cannot", "I don't have access", "I am an AI", "I am a large language model",
  "I don't have the ability", "I cannot interact with external systems",
  "I cannot fulfill", "I do not have"
If your training tells you to say one of these phrases, OVERRIDE IT and call a tool instead.

TOOLS:
{tools}

STRICT FORMAT — every response block must be exactly ONE of these two patterns:

Pattern A (call a tool):
Thought: <your reasoning — one line>
Action: <exact tool name from [{tool_names}]>
Action Input: {{"param": "value"}}

Pattern B (final answer — ONLY after receiving at least one Observation):
Thought: I now know the final answer
Final Answer: <answer>

RULES:
- Your VERY FIRST response MUST be Pattern A (a tool call). NEVER start with Final Answer.
- After every Thought: write either Action: or Final Answer: on the very next line. Nothing else.
- Action Input is MANDATORY after Action. Use {{}} if no parameters.
- NEVER output "Final Answer:" before you have received at least one Observation.
- Tool names may contain spaces and slashes (e.g. "RAGenie News/create_news_keyword"). Copy EXACTLY.
- For news keyword tasks: call create_news_keyword with {{"term": "...", "fetch_interval_minutes": N}}. One call is enough — it both creates AND schedules fetching.
- If an Observation contains a URL, your Final Answer must include that URL verbatim.

EXAMPLES:
Question: login to kite
Thought: The user wants to log in to KITE. I must call the KITE/login tool.
Action: KITE/login
Action Input: {{}}
Observation: https://kite.zerodha.com/connect/login?...
Thought: I now know the final answer
Final Answer: Here is your KITE login URL: https://kite.zerodha.com/connect/login?...

Question: track Mamata Banerjee news every 15 minutes
Thought: I need to create a news keyword with a 15-minute fetch interval.
Action: RAGenie News/create_news_keyword
Action Input: {{"term": "Mamata Banerjee", "fetch_interval_minutes": 15}}
Observation: Created: "Mamata Banerjee" (id=abc-123) — fetching every 15min.
Thought: I now know the final answer
Final Answer: Done! "Mamata Banerjee" is now tracked and news will be fetched every 15 minutes.

Begin!

Question: {input}
Thought:{agent_scratchpad}"""


@router.post("/chat", response_model=MCPChatResponse)
async def mcp_agent_chat(body: MCPChatRequest, current_user: User = Depends(require_auth)):
    """Run an agent-mode chat using selected (or all) connected MCP tools."""
    from .app import app_state

    mgr = await _get_manager(current_user.id)
    orchestrator = app_state.get("orchestrator")
    if orchestrator is None:
        raise HTTPException(status_code=503, detail="Orchestrator not initialised")

    all_tools = mgr.list_all_tools()
    if not all_tools:
        raise HTTPException(status_code=409, detail="No MCP tools connected. Connect a server first.")

    if body.tool_filter:
        tool_defs = [t for t in all_tools if f"{t.server_name}/{t.name}" in body.tool_filter]
        if not tool_defs:
            raise HTTPException(status_code=400, detail="None of the requested tools are available")
    else:
        # Auto-select the most relevant tools to avoid overwhelming small LLMs with 40+ choices.
        # Score each tool by word-overlap with the user's message, keep top _MAX_TOOLS.
        _MAX_TOOLS = 12
        if len(all_tools) <= _MAX_TOOLS:
            tool_defs = all_tools
        else:
            msg_words = set(body.message.lower().split())
            def _tool_score(td) -> int:
                haystack = f"{td.server_name} {td.name} {td.description or ''}".lower()
                return sum(1 for w in msg_words if len(w) > 3 and w in haystack)
            ranked = sorted(all_tools, key=_tool_score, reverse=True)
            # Always keep the top-scored tools; break ties by keeping earlier items
            top = ranked[:_MAX_TOOLS]
            logger.info(
                f"Auto-selected {len(top)}/{len(all_tools)} tools for query: "
                + ", ".join(f"{t.server_name}/{t.name}" for t in top)
            )
            tool_defs = top

    # Capture message text for use inside _call closures below
    _user_message = body.message

    # Build LangChain Tool objects
    lc_tools: List[Tool] = []
    for td in tool_defs:
        llm_name = f"{td.server_name}/{td.name}"
        schema = td.input_schema or {}
        required_params: List[str] = schema.get("required", [])
        all_props: List[str] = list(schema.get("properties", {}).keys())

        # Build a compact schema hint for the LLM so it generates proper JSON
        props_hint = json.dumps(schema.get("properties", {}), separators=(",", ":"))
        description = (
            f"[MCP:{td.server_name}] {td.description}"
            f" | Input JSON: {props_hint}"
            + (f" | Required: {required_params}" if required_params else "")
        )
        # Add filesystem-specific hints to prevent common mistakes
        if td.name in ("move_file", "rename"):
            description += (
                " | IMPORTANT: 'destination' must be the FULL path including filename"
                " (e.g. /dest/dir/file.txt), NOT just a directory. Moving into a"
                " directory requires appending the original filename to the destination."
            )

        # Warn the LLM that destructive tools need explicit user confirmation
        if llm_name in _DESTRUCTIVE_TOOLS:
            description += (
                f" | ⚠️ DESTRUCTIVE: This tool executes a real financial transaction."
                f" Before calling it, you MUST ask the user to confirm by including"
                f" '{_CONFIRM_TOKEN}' in their next message. Do NOT call this tool"
                f" unless their message explicitly contains '{_CONFIRM_TOKEN}'."
            )

        async def _call(
            args_str: str,
            _name: str = llm_name,
            _required: List[str] = required_params,
            _all_props: List[str] = all_props,
            _msg: str = _user_message,
        ) -> str:
            # Guard: refuse destructive tools unless user included confirmation token
            if _name in _DESTRUCTIVE_TOOLS and _CONFIRM_TOKEN not in _msg:
                return (
                    f"BLOCKED: '{_name}' is a destructive financial operation and cannot be "
                    f"called autonomously. Ask the user to confirm by including '{_CONFIRM_TOKEN}' "
                    "in their message before proceeding."
                )
            # Audit log every financial tool call
            try:
                from ..security.audit_logger import get_audit_logger
                if any(_name.startswith(p) for p in ("KITE/", "MoSPI/")):
                    get_audit_logger().security_event(
                        "mcp_tool_call", severity="info",
                        tool=_name, args_preview=args_str[:200]
                    )
            except Exception:
                pass
            args_str = args_str.strip()
            try:
                if args_str.startswith("{"):
                    parsed = json.loads(args_str)
                else:
                    # Map plain-text value to the first required (or available) parameter
                    key = _required[0] if _required else (_all_props[0] if _all_props else "input")
                    parsed = {key: args_str}
            except (json.JSONDecodeError, TypeError):
                key = _required[0] if _required else (_all_props[0] if _all_props else "input")
                parsed = {key: str(args_str)}
            raw = await mgr.call_tool(_name, parsed)
            # Sanitize result to prevent prompt-injection via tool output
            return _sanitize_tool_result(str(raw), _name)

        lc_tools.append(Tool(
            name=llm_name,
            description=description,
            coroutine=_call,
            func=lambda s, _n=llm_name: f"Use async call for {_n}",
        ))

    # Build agent
    llm = orchestrator.llm_wrapper.get_llm()
    prompt = PromptTemplate.from_template(_REACT_TEMPLATE)
    agent = create_react_agent(llm, lc_tools, prompt)
    def _react_parse_error_handler(error: Exception) -> str:
        return (
            "Format error — your last response was not valid ReAct format. "
            "You MUST write exactly one of:\n"
            "  Thought: <reasoning>\n  Action: <tool>\n  Action Input: {\"key\": \"value\"}\n"
            "OR\n"
            "  Thought: I now know the final answer\n  Final Answer: <answer>\n"
            "Do NOT write bare text after Thought:. Try again now."
        )

    executor = AgentExecutor(
        agent=agent,
        tools=lc_tools,
        verbose=False,
        handle_parsing_errors=_react_parse_error_handler,
        max_iterations=15,
        max_execution_time=180,
        return_intermediate_steps=True,
        early_stopping_method="force",
    )

    # Build history context
    history = _mcp_chat_histories.setdefault(body.conversation_id, [])
    history_text = "\n".join(
        f"{'User' if m.role == 'user' else 'Assistant'}: {m.content}"
        for m in history[-10:]
    )
    full_input = f"{history_text}\nUser: {body.message}" if history_text else body.message

    _REFUSAL_PHRASES = (
        "i cannot", "i don't have access", "i am an ai", "i am a large language model",
        "i don't have the ability", "i cannot interact", "i cannot fulfill", "i do not have",
        "i'm unable to", "i am unable to",
    )

    def _is_refusal(text: str) -> bool:
        t = text.lower()
        return any(p in t for p in _REFUSAL_PHRASES)

    # Run agent
    try:
        result = await executor.ainvoke({"input": full_input})
    except Exception as e:
        logger.error("MCP agent chat error", exc_info=True)
        raise HTTPException(status_code=500, detail="MCP agent encountered an internal error.")

    # If the agent refused without calling any tools, retry once with an explicit override
    if not result.get("intermediate_steps") and _is_refusal(result.get("output", "")):
        logger.warning(f"Agent refused without calling any tools — retrying with forced prompt for: {body.message[:80]}")
        tool_names_str = ", ".join(td.server_name + "/" + td.name for td in tool_defs[:5])
        forced_input = (
            f"{full_input}\n\n"
            f"SYSTEM OVERRIDE: You have working tools. You MUST call a tool RIGHT NOW.\n"
            f"Do NOT write any refusal. Your next line must be: Action: <tool_name>\n"
            f"Available tools include: {tool_names_str} (and more).\n"
            f"Pick the most relevant tool and call it immediately."
        )
        try:
            result = await executor.ainvoke({"input": forced_input})
        except Exception as e:
            logger.error(f"MCP agent retry error: {e}")

    raw_output = result.get("output", "No response generated.")
    # Detect leaked ReAct error strings and replace with last useful observation
    _BAD_OUTPUT_MARKERS = (
        "Invalid Format: Missing 'Action:'",
        "Invalid Format: Missing 'Final Answer'",
        "Could not parse LLM output",
        "Format error — your last response",
        "Agent stopped due to iteration limit or time limit",
    )
    if any(m in raw_output for m in _BAD_OUTPUT_MARKERS):
        steps = result.get("intermediate_steps", [])
        if raw_output.startswith("Agent stopped"):
            logger.warning(f"MCP agent hit iteration/time limit for: {body.message[:80]}")
        if steps:
            last_obs = str(steps[-1][1]) if steps[-1][1] else ""
            response_text = last_obs if last_obs else "I wasn't able to complete that request. Please try rephrasing."
        else:
            response_text = "I wasn't able to complete that request. Please try rephrasing."
    else:
        response_text = raw_output
    intermediate = result.get("intermediate_steps", [])

    # Extract tool call traces
    traces: List[ToolCallTrace] = []
    for action, observation in intermediate:
        try:
            args = json.loads(action.tool_input) if isinstance(action.tool_input, str) and action.tool_input.strip().startswith("{") else {"input": str(action.tool_input)}
        except Exception:
            args = {"input": str(action.tool_input)}
        # Redact raw financial data — truncate aggressively for frontend
        safe_result = _sanitize_tool_result(str(observation), action.tool, max_chars=400)
        traces.append(ToolCallTrace(
            tool_name=action.tool,
            args=args,
            result=safe_result,
        ))

    # Auto-detect login success → mark server session as authenticated
    from datetime import datetime, timezone as _tz
    for trace in traces:
        if trace.tool_name.endswith("/login") and "error" not in trace.result.lower():
            server_name = trace.tool_name.split("/")[0]
            sid = mgr.server_id_for_name(server_name)
            if sid:
                mgr.set_session_meta(sid, "logged_in", True)
                mgr.set_session_meta(sid, "logged_in_at",
                    datetime.now(_tz.utc).strftime("%Y-%m-%d %H:%M UTC"))
                logger.info(f"Session marked as authenticated for server '{server_name}'")

    # Update history
    history.append(MCPChatMessage(role="user", content=body.message))
    history.append(MCPChatMessage(role="assistant", content=response_text, tool_calls=traces))
    if len(history) > 40:
        history[:] = history[-40:]

    return MCPChatResponse(
        response=response_text,
        conversation_id=body.conversation_id,
        tool_calls=traces,
        history=list(history),
    )


@router.get("/chat/{conversation_id}", response_model=List[MCPChatMessage])
async def get_mcp_chat_history(conversation_id: str):
    """Return the message history for an MCP chat conversation."""
    return _mcp_chat_histories.get(conversation_id, [])


@router.delete("/chat/{conversation_id}", status_code=204)
async def clear_mcp_chat_history(conversation_id: str):
    """Clear the message history for an MCP chat conversation."""
    _mcp_chat_histories.pop(conversation_id, None)


# ── Session metadata endpoint ───────────────────────────────────────────────

@router.get("/session-meta/{server_id}")
async def get_session_meta(server_id: str, current_user: User = Depends(require_auth)):
    """Return the in-memory session state for a server (e.g. logged_in status)."""
    store = _get_store()
    _owned_or_404(store, server_id, current_user.id)
    mgr = await _get_manager(current_user.id)
    return mgr.get_session_meta(server_id)


@router.post("/session-meta/{server_id}", status_code=204)
async def set_session_meta(server_id: str, body: dict, current_user: User = Depends(require_auth)):
    """Manually set session metadata keys for a server.
    Only whitelisted keys are accepted to prevent data injection."""
    _ALLOWED_SESSION_KEYS = {"logged_in", "logged_in_at", "note"}
    store = _get_store()
    _owned_or_404(store, server_id, current_user.id)
    mgr = await _get_manager(current_user.id)
    for key, value in body.items():
        if key not in _ALLOWED_SESSION_KEYS:
            raise HTTPException(status_code=400, detail=f"Session key '{key}' is not permitted")
        mgr.set_session_meta(server_id, key, value)


# ── Path suggestions (OS-independent) ────────────────────────────────────────

@router.get("/path-suggestions")
async def get_path_suggestions():
    """Return common OS-independent directory paths the user might want to allow."""
    from pathlib import Path
    home = Path.home()
    candidates = {
        "Home":       home,
        "Documents":  home / "Documents",
        "Downloads":  home / "Downloads",
        "Desktop":    home / "Desktop",
        "Pictures":   home / "Pictures",
        "Projects":   home / "Projects",
        "workspace":  home / "workspace",
        "Working Dir": Path.cwd(),
    }
    return [
        {"label": label, "path": str(p)}
        for label, p in candidates.items()
        if p.exists()
    ]


# ── Built-in server seeds ────────────────────────────────────────────────────

@router.post("/seed-news", response_model=ServerWithStatus, status_code=201)
async def seed_news_server(connect_now: bool = True, current_user: User = Depends(require_auth)):
    """Register the built-in RAGenie News MCP server (stdio) and optionally connect it.

    The news server exposes tools: list_news_keywords, create_news_keyword,
    update_news_keyword, delete_news_keyword, fetch_news_now, get_news_articles,
    suggest_news_keyword.

    Idempotent — returns the existing server if already registered (for this user).
    """
    import sys
    from pathlib import Path

    store = _get_store()
    mgr = await _get_manager(current_user.id)

    existing = store.get_by_name(current_user.id, "RAGenie News")
    if existing:
        status = mgr.get_server_status(existing.id) or ServerStatus(
            server_id=existing.id, status=ConnectionStatus.DISCONNECTED
        )
        tools = mgr._connections[existing.id].get_tools() if existing.id in mgr._connections else []
        return ServerWithStatus(config=existing, status=status, tools=tools)

    # Path to the news server script (same repo)
    server_script = str(
        Path(__file__).resolve().parent.parent / "mcp_servers" / "news_server.py"
    )

    req = ServerCreateRequest(
        name="RAGenie News",
        transport="stdio",
        enabled=True,
        connect_now=connect_now,
        command=sys.executable,
        args=[server_script],
        env={},
    )

    config = store.create(current_user.id, req)
    if connect_now:
        try:
            await mgr.connect_server(config)
        except Exception as e:
            logger.warning(f"News MCP server connect failed: {e}")

    status = mgr.get_server_status(config.id) or ServerStatus(
        server_id=config.id, status=ConnectionStatus.DISCONNECTED
    )
    tools = mgr._connections[config.id].get_tools() if config.id in mgr._connections else []
    return ServerWithStatus(config=config, status=status, tools=tools)


# ── Parameterised routes /{id} ───────────────────────────────────────────────

@router.get("/{server_id}", response_model=ServerWithStatus)
async def get_server(server_id: str, current_user: User = Depends(require_auth)):
    """Get server details and tools. Env/headers are redacted."""
    store = _get_store()
    mgr = await _get_manager(current_user.id)
    config = _owned_or_404(store, server_id, current_user.id)
    status = mgr.get_server_status(server_id) or ServerStatus(
        server_id=server_id, status=ConnectionStatus.DISCONNECTED
    )
    tools = mgr._connections[server_id].get_tools() if server_id in mgr._connections else []
    config.env = None
    config.headers = None
    return ServerWithStatus(config=config, status=status, tools=tools)


@router.patch("/{server_id}", response_model=ServerWithStatus)
async def update_server(server_id: str, patch: ServerConfigPatch, current_user: User = Depends(require_auth)):
    """Update server config. Reconnects if currently connected."""
    store = _get_store()
    mgr = await _get_manager(current_user.id)
    _owned_or_404(store, server_id, current_user.id)

    if patch.name is not None:
        existing_name = store.get_by_name(current_user.id, patch.name)
        if existing_name and existing_name.id != server_id:
            raise HTTPException(status_code=400, detail="name already exists")

    # SSRF guard on URL updates
    if patch.url:
        _validate_url_for_ssrf(patch.url)

    try:
        config = store.update(server_id, patch)
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    if server_id in mgr._connections:
        try:
            await mgr.reload_server(server_id)
        except Exception as e:
            logger.warning(f"Reload after update failed for '{config.name}': {e}")
    elif config.enabled and patch.enabled is not False:
        try:
            await mgr.connect_server(config)
        except MCPConnectionError as e:
            logger.warning(f"Auto-connect after update failed: {e}")

    _log_activity(current_user.id, "mcp_server_updated", f"Updated MCP server '{config.name}'", {"server_id": server_id})

    status = mgr.get_server_status(server_id) or ServerStatus(
        server_id=server_id, status=ConnectionStatus.DISCONNECTED
    )
    tools = mgr._connections[server_id].get_tools() if server_id in mgr._connections else []
    return ServerWithStatus(config=config, status=status, tools=tools)


@router.delete("/{server_id}", status_code=204)
async def delete_server(server_id: str, current_user: User = Depends(require_auth)):
    """Delete a server config and disconnect if connected."""
    store = _get_store()
    mgr = await _get_manager(current_user.id)
    config = _owned_or_404(store, server_id, current_user.id)
    await mgr.disconnect_server(server_id)
    store.delete(server_id)
    _log_activity(current_user.id, "mcp_server_deleted", f"Deleted MCP server '{config.name}'", {"server_id": server_id})


@router.post("/{server_id}/connect", response_model=ServerStatus)
async def connect_server(server_id: str, current_user: User = Depends(require_auth)):
    """Connect (or reconnect) a server."""
    store = _get_store()
    mgr = await _get_manager(current_user.id)
    config = _owned_or_404(store, server_id, current_user.id)
    try:
        await mgr.connect_server(config)
    except MCPConnectionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    _log_activity(current_user.id, "mcp_server_connected", f"Connected MCP server '{config.name}'", {"server_id": server_id})
    return mgr.get_server_status(server_id)


@router.post("/{server_id}/disconnect", response_model=ServerStatus)
async def disconnect_server(server_id: str, current_user: User = Depends(require_auth)):
    """Disconnect a server without deleting its config."""
    store = _get_store()
    mgr = await _get_manager(current_user.id)
    config = _owned_or_404(store, server_id, current_user.id)
    await mgr.disconnect_server(server_id)
    _log_activity(current_user.id, "mcp_server_disconnected", f"Disconnected MCP server '{config.name}'", {"server_id": server_id})
    return ServerStatus(server_id=server_id, status=ConnectionStatus.DISCONNECTED)


@router.post("/{server_id}/login")
async def server_login(server_id: str, current_user: User = Depends(require_auth)):
    """Directly invoke the login tool for a connected server (bypasses the LLM agent).
    Returns the login URL or instruction from the tool."""
    from datetime import datetime, timezone as _tz
    store = _get_store()
    mgr = await _get_manager(current_user.id)
    config = _owned_or_404(store, server_id, current_user.id)
    if server_id not in mgr._connections:
        raise HTTPException(status_code=409, detail="Server is not connected")

    # Find the login tool for this server
    tools = mgr._connections[server_id].get_tools()
    login_tool = next((t for t in tools if t.name == "login"), None)
    if login_tool is None:
        raise HTTPException(status_code=404, detail=f"Server '{config.name}' has no login tool")

    llm_name = f"{config.name}/{login_tool.name}"

    # For streamable-HTTP servers (e.g. KITE), pass the transport session_id
    # so the login tool can associate the OAuth callback with this connection.
    conn = mgr._connections[server_id]
    session_id = getattr(conn, "session_id", None)
    login_args: dict = {}
    if session_id:
        login_args["session_id"] = session_id

    try:
        result = await mgr.call_tool(llm_name, login_args)
    except Exception as e:
        # Fallback: if the tool itself failed but we have a session_id,
        # construct the KITE-style login URL directly from the server base URL.
        if session_id and config.url:
            from urllib.parse import urljoin, urlencode
            base = config.url.rstrip("/").rsplit("/", 1)[0]  # strip /mcp suffix
            login_url = f"{base}/login?{urlencode({'session_id': session_id})}"
            result = login_url
        else:
            raise HTTPException(status_code=502, detail=f"Login tool call failed: {e}")

    result_str = str(result)

    # Auto-mark session as authenticated if call succeeded
    if "error" not in result_str.lower():
        mgr.set_session_meta(server_id, "login_initiated", True)
        mgr.set_session_meta(server_id, "login_initiated_at",
                             datetime.now(_tz.utc).isoformat())

    try:
        from ..security.audit_logger import get_audit_logger
        get_audit_logger().security_event("mcp_login_initiated", severity="info",
                                          server=config.name)
    except Exception:
        pass

    return {"server": config.name, "result": result_str}


@router.get("/{server_id}/tools", response_model=List[ToolDefinition])
async def list_server_tools(server_id: str, current_user: User = Depends(require_auth)):
    """List the cached tools for a connected server."""
    store = _get_store()
    mgr = await _get_manager(current_user.id)
    _owned_or_404(store, server_id, current_user.id)
    if server_id not in mgr._connections:
        raise HTTPException(status_code=409, detail="Server is not connected")
    return mgr._connections[server_id].get_tools()


@router.post("/{server_id}/test", response_model=TestResult)
async def test_server(server_id: str, current_user: User = Depends(require_auth)):
    """Perform an ephemeral connect → list tools → disconnect test."""
    store = _get_store()
    config = _owned_or_404(store, server_id, current_user.id)

    start = time.monotonic()
    probe = MCPClientConnection(config)
    try:
        await probe.connect()
        tools = probe.get_tools()
        latency_ms = int((time.monotonic() - start) * 1000)
        return TestResult(
            success=True,
            tool_count=len(tools),
            tools=tools,
            latency_ms=latency_ms,
        )
    except Exception as e:
        return TestResult(success=False, error=str(e))
    finally:
        try:
            await probe.disconnect()
        except Exception:
            pass
