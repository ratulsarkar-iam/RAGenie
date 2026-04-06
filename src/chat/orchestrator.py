from typing import List, Dict, Any, Optional
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

logger = get_logger(__name__)


class ChatOrchestrator:
    """Orchestrate chat interactions with RAG and search capabilities."""
    
    def __init__(
        self,
        llm_wrapper: LangChainLLM,
        rag_store: PageIndexStore,
        search_service: SearchService,
        max_history: int = 10
    ):
        self.llm_wrapper = llm_wrapper
        self.rag_store = rag_store
        self.search_service = search_service
        self.context_builder = ContextBuilder()
        self.max_history = max_history
        self.conversation: Optional[Conversation] = None
        
        # Create tools
        self.tools = self._create_tools()
        
        # Create agent
        self.agent = self._create_agent()
    
    def _create_tools(self) -> List[Tool]:
        """Create LangChain tools for the agent."""
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
        
        return tools
    
    def _create_agent(self) -> AgentExecutor:
        """Create a LangChain agent with tools."""
        # Get the ReAct prompt from LangChain hub
        try:
            prompt = hub.pull("hwchase17/react")
        except Exception as e:
            logger.warning(f"Could not pull prompt from hub: {e}. Using fallback prompt.")
            # Fallback to a simple prompt if hub is unavailable
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
        
        # Create agent
        llm = self.llm_wrapper.get_llm()
        agent = create_react_agent(llm, self.tools, prompt)
        
        # Create executor
        agent_executor = AgentExecutor(
            agent=agent,
            tools=self.tools,
            verbose=True,
            handle_parsing_errors=True,
            max_iterations=5
        )
        
        return agent_executor
    
    def start_conversation(self, conversation_id: str) -> Conversation:
        """Start a new conversation.
        
        Args:
            conversation_id: Unique conversation identifier
            
        Returns:
            Conversation object
        """
        self.conversation = Conversation(conversation_id=conversation_id)
        logger.info(f"Started conversation: {conversation_id}")
        return self.conversation
    
    def chat(self, user_message: str) -> str:
        """Process a user message and generate a response.
        
        Args:
            user_message: User's message
            
        Returns:
            Assistant's response
        """
        if self.conversation is None:
            raise ValueError("No active conversation. Call start_conversation() first.")
        
        logger.info(f"Processing message: {user_message}")
        
        # Add user message to conversation
        self.conversation.add_message("user", user_message)
        
        try:
            # Use agent to process the message
            response = self.agent.invoke({"input": user_message})
            assistant_message = response.get("output", "I apologize, but I couldn't generate a response.")
            
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            assistant_message = f"I encountered an error: {str(e)}"
        
        # Add assistant message to conversation
        self.conversation.add_message("assistant", assistant_message)
        
        # Prune history if needed
        self._prune_history()
        
        logger.info("Response generated successfully")
        return assistant_message
    
    def chat_simple(self, user_message: str, use_reasoning: bool = False) -> str:
        """Simple chat without agent (direct LLM call with RAG).
        
        Args:
            user_message: User's message
            use_reasoning: Whether to use reasoning model (multi-model mode only)
            
        Returns:
            Assistant's response
        """
        if self.conversation is None:
            raise ValueError("No active conversation. Call start_conversation() first.")
        
        logger.info(f"Processing simple message: {user_message}")
        
        # Add user message
        self.conversation.add_message("user", user_message)
        
        try:
            # Search RAG for context
            chunks = self.rag_store.search_chunks(user_message, top_k=5)
            
            # Build prompt with context and history
            history = self._format_history(exclude_last_user=True)
            
            if chunks:
                context = self.context_builder.build_context(chunks)
                prompt = f"""{SYSTEM_PROMPT}

{f"## Conversation History\n{history}\n" if history else ""}## Retrieved Context
Use the following context to answer the question. If the context doesn't contain relevant information, answer based on your general knowledge.

{context}

## Current Message
User: {user_message}

Assistant:"""
            else:
                prompt = f"""{SYSTEM_PROMPT}

{f"## Conversation History\n{history}\n" if history else ""}## Current Message
User: {user_message}

Assistant:"""
            
            # Generate response with optional reasoning
            logger.info(f"Generating response (reasoning: {use_reasoning})")
            response = self.llm_wrapper.generate(prompt, use_reasoning=use_reasoning)
            
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            response = f"I encountered an error: {str(e)}"
        
        # Add assistant message
        self.conversation.add_message("assistant", response)
        
        # Prune history
        self._prune_history()
        
        logger.info("Simple response generated successfully")
        return response
    
    def chat_with_reasoning(self, user_message: str) -> Dict[str, str]:
        """Chat with explicit reasoning step (multi-model mode only).
        
        Args:
            user_message: User's message
            
        Returns:
            Dictionary with 'reasoning' and 'response' keys
        """
        if self.conversation is None:
            raise ValueError("No active conversation. Call start_conversation() first.")
        
        logger.info(f"Processing message with reasoning: {user_message}")
        
        # Add user message
        self.conversation.add_message("user", user_message)
        
        try:
            # Search RAG for context
            chunks = self.rag_store.search_chunks(user_message, top_k=5)
            
            # Build prompt with context and history
            history = self._format_history(exclude_last_user=True)
            
            if chunks:
                context = self.context_builder.build_context(chunks)
                prompt = f"""{SYSTEM_PROMPT}

{f"## Conversation History\n{history}\n" if history else ""}## Retrieved Context
Use the following context to answer the question. If the context doesn't contain relevant information, answer based on your general knowledge.

{context}

## Current Message
User: {user_message}

Assistant:"""
            else:
                prompt = f"""{SYSTEM_PROMPT}

{f"## Conversation History\n{history}\n" if history else ""}## Current Message
User: {user_message}

Assistant:"""
            
            # Generate with reasoning
            reasoning, response = self.llm_wrapper.generate_with_reasoning(prompt)
            
            result = {
                "reasoning": reasoning,
                "response": response
            }
            
        except Exception as e:
            logger.error(f"Error generating response with reasoning: {str(e)}")
            result = {
                "reasoning": "",
                "response": f"I encountered an error: {str(e)}"
            }
        
        # Add assistant message
        self.conversation.add_message("assistant", result["response"])
        
        # Prune history
        self._prune_history()
        
        logger.info("Response with reasoning generated successfully")
        return result
    
    def _format_history(self, exclude_last_user: bool = True, max_chars_per_msg: int = 500) -> str:
        """Format conversation history as a chat transcript for the LLM.
        
        Args:
            exclude_last_user: If True, exclude the last user message (since it's the current query).
            max_chars_per_msg: Truncate long messages to avoid blowing up context window.
            
        Returns:
            Formatted conversation history string, or empty string if no history.
        """
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
            # Keep only the most recent messages
            self.conversation.messages = self.conversation.messages[-self.max_history:]
            logger.debug(f"Pruned conversation history to {self.max_history} messages")
    
    def get_conversation_history(self) -> List[Dict[str, Any]]:
        """Get the conversation history.
        
        Returns:
            List of message dictionaries
        """
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
