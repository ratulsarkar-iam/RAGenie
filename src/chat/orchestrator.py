import asyncio
import json
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

logger = get_logger(__name__)

_REACT_PROMPT_CACHE = None  # pulled once; reused on every rebuild_tools


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
    ):
        self.llm_wrapper = llm_wrapper
        self.rag_store = rag_store
        self.search_service = search_service
        self.context_builder = ContextBuilder()
        self.max_history = max_history
        self.conversation: Optional[Conversation] = None
        self.memory_manager: Optional[MemoryManager] = memory_manager
        self._mcp_client_manager: Optional["MCPClientManager"] = mcp_client_manager
        
        # Create tools
        self.tools = self._create_tools()
        
        # Create agent
        self.agent = self._create_agent()
    
    def _create_tools(self) -> List[Tool]:
        """Create LangChain tools for the agent (built-in + MCP)."""
        tools = []
        
        # RAG search tool
        def rag_search(query: str) -> str:
            """Search the knowledge base for relevant information."""
            try:
                chunks = self.rag_store.search_chunks(query, top_k=5)
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

        # MCP external tools
        if self._mcp_client_manager:
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

        return tools

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
    
    def chat(self, user_message: str) -> str:
        """Process a user message using the LangChain agent (sync)."""
        if self.conversation is None:
            raise ValueError("No active conversation. Call start_conversation() first.")
        
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

    async def achat(self, user_message: str, callbacks: Optional[List] = None) -> str:
        """Async agent mode — supports MCP coroutine tools properly."""
        if self.conversation is None:
            raise ValueError("No active conversation. Call start_conversation() first.")

        logger.info(f"Processing agent message (async): {user_message}")
        self.conversation.add_message("user", user_message)

        _STOP_SENTINEL = "Agent stopped due to iteration limit or time limit"
        try:
            invoke_kwargs: Dict[str, Any] = {"input": user_message}
            cfg = {"callbacks": callbacks} if callbacks else {}
            response = await self.agent.ainvoke(invoke_kwargs, config=cfg)
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
            logger.error(f"Error generating async agent response: {str(e)}")
            assistant_message = f"I encountered an error: {str(e)}"

        self.conversation.add_message("assistant", assistant_message)
        self._prune_history()
        logger.info("Async agent response generated successfully")
        return assistant_message
    
    def chat_simple(self, user_message: str, use_reasoning: bool = False) -> str:
        """Simple chat without agent (direct LLM call with RAG and memory context)."""
        if self.conversation is None:
            raise ValueError("No active conversation. Call start_conversation() first.")

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
            raw_chunks = self.rag_store.search_chunks(user_message, top_k=5)

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
            raw_chunks = self.rag_store.search_chunks(user_message, top_k=5)
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
