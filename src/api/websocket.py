from fastapi import WebSocket, WebSocketDisconnect, Query
from typing import Any, Dict, List, Optional
import json
import asyncio
from langchain.callbacks.base import AsyncCallbackHandler
from ..core.logging_config import get_logger
from ..utils.reasoning_detector import detect_reasoning_needed
from ..security.ws_security import validate_ws_message, check_ws_rate_limit, cleanup_client
from ..security.audit_logger import get_audit_logger
from ..security.document_filter import filter_document_chunk
from ..security.prompt_builder import build_secure_prompt

logger = get_logger(__name__)


class ConnectionManager:
    """Manage WebSocket connections."""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, client_id: str):
        """Accept a new WebSocket connection."""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info(f"Client {client_id} connected")
    
    def disconnect(self, client_id: str):
        """Remove a WebSocket connection."""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            logger.info(f"Client {client_id} disconnected")
    
    async def send_message(self, client_id: str, message: dict):
        """Send a message to a specific client."""
        if client_id in self.active_connections:
            websocket = self.active_connections[client_id]
            await websocket.send_json(message)
    
    async def send_text(self, client_id: str, text: str):
        """Send text to a specific client."""
        if client_id in self.active_connections:
            websocket = self.active_connections[client_id]
            await websocket.send_text(text)


manager = ConnectionManager()


class ToolCallStreamingCallback(AsyncCallbackHandler):
    """Sends tool_call / tool_result / tool_error events to the WebSocket client."""

    def __init__(self, client_id: str):
        super().__init__()
        self.client_id = client_id
        self._current_tool: Optional[str] = None

    async def on_tool_start(
        self, serialized: Dict[str, Any], input_str: str, **kwargs: Any
    ) -> None:
        self._current_tool = serialized.get("name", "unknown_tool")
        await manager.send_message(self.client_id, {
            "type": "tool_call",
            "tool": self._current_tool,
            "args": input_str,
        })

    async def on_tool_end(self, output: Any, **kwargs: Any) -> None:
        result_str = (
            output.content if hasattr(output, "content") else str(output)
        )[:800]
        await manager.send_message(self.client_id, {
            "type": "tool_result",
            "tool": self._current_tool or "unknown_tool",
            "result": result_str,
        })
        self._current_tool = None

    async def on_tool_error(self, error: Exception, **kwargs: Any) -> None:
        await manager.send_message(self.client_id, {
            "type": "tool_error",
            "tool": self._current_tool or "unknown_tool",
            "error": str(error),
        })
        self._current_tool = None


async def handle_chat_websocket(websocket: WebSocket, client_id: str, orchestrator, current_user=None):
    """Handle WebSocket chat connection with streaming. `current_user` must be pre-validated by the caller."""
    await manager.connect(websocket, client_id)
    user_id = current_user.id if current_user else None

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()

            # --- Security: validate message structure ---
            is_valid, error_msg = validate_ws_message(data)
            if not is_valid:
                get_audit_logger().ws_invalid_message(client_id=client_id, reason=error_msg)
                await manager.send_message(client_id, {"type": "error", "content": error_msg})
                continue

            # --- Security: rate limit per client ---
            allowed, retry_after = check_ws_rate_limit(client_id)
            if not allowed:
                get_audit_logger().ws_rate_limit_hit(client_id=client_id)
                await manager.send_message(client_id, {
                    "type": "error",
                    "content": f"Rate limit exceeded. Retry after {retry_after}s."
                })
                continue

            message = data.get("message", "")
            conversation_id = data.get("conversation_id", "default")
            use_agent = data.get("use_agent", False)
            use_reasoning = data.get("use_reasoning", False)
            model_override_name = data.get("model")  # optional per-request model (e.g. voice)
            
            # Auto-detect reasoning if not explicitly set
            if not use_reasoning and detect_reasoning_needed(message):
                use_reasoning = True
                logger.info(f"Auto-detected reasoning needed for: {message[:50]}...")
            
            logger.info(f"WebSocket message from {client_id} (len={len(message)}, reasoning={use_reasoning})")
            
            # Start or resume conversation
            if orchestrator.conversation is None or orchestrator.conversation.conversation_id != conversation_id:
                orchestrator.start_conversation(conversation_id)
            
            # NOTE: user message is added inside achat() / stream_simple_response().
            # Do NOT add it here to avoid double-insertion in agent mode.
            
            # Send acknowledgment
            await manager.send_message(client_id, {
                "type": "user_message",
                "content": message
            })

            if user_id:
                try:
                    from .app import app_state
                    activity_logger = app_state.get("activity_logger")
                    if activity_logger:
                        activity_logger.log(
                            user_id, "chat_message",
                            f"Sent chat message via WS ({'agent' if use_agent else 'reasoning' if use_reasoning else 'simple'})",
                            {"conversation_id": conversation_id},
                        )
                except Exception:
                    pass
            
            try:
                # Build a one-off LLM override when the client requests a specific model
                llm_override = None
                if model_override_name:
                    try:
                        from langchain_community.llms import Ollama
                        llm_override = Ollama(
                            model=model_override_name,
                            base_url="http://localhost:11434",
                        )
                        logger.info(f"Using model override: {model_override_name}")
                    except Exception as _oe:
                        logger.warning(f"Could not create model override '{model_override_name}': {_oe}")

                # Generate response with streaming
                if use_agent:
                    logger.info(f"WebSocket agent mode activated for: {message[:50]}...")
                    tool_callback = ToolCallStreamingCallback(client_id)
                    response = await orchestrator.achat(
                        message, callbacks=[tool_callback], llm_override=llm_override, user_id=user_id
                    )
                    await manager.send_message(client_id, {
                        "type": "assistant_message",
                        "content": response,
                        "done": True
                    })
                elif use_reasoning:
                    # Reasoning mode - use streaming with multi-model
                    logger.info(f"WebSocket reasoning mode activated for: {message[:50]}...")
                    try:
                        # Send start signal
                        await manager.send_message(client_id, {
                            "type": "stream_start"
                        })
                        
                        # Get reasoning model response
                        if orchestrator.llm_wrapper.is_multi_model and orchestrator.llm_wrapper._multi_model_manager:
                            if "reasoning" in orchestrator.llm_wrapper._multi_model_manager.models:
                                # Add user message once for the reasoning path
                                orchestrator.conversation.add_message("user", message)

                                # Notify reasoning phase
                                await manager.send_message(client_id, {
                                    "type": "reasoning",
                                    "content": ""
                                })
                                
                                # Get reasoning from reasoning model
                                reasoning_model = orchestrator.llm_wrapper._multi_model_manager.models["reasoning"]
                                chunks = orchestrator.rag_store.search_chunks(message, top_k=5, user_id=user_id)
                                
                                # Build reasoning prompt
                                from ..rag.context_builder import ContextBuilder
                                from ..llm.prompts import SYSTEM_PROMPT
                                context_builder = ContextBuilder()
                                
                                history = orchestrator._format_history(exclude_last_user=True)
                                
                                if chunks:
                                    context = context_builder.build_context(chunks)
                                    reasoning_prompt = f"""{SYSTEM_PROMPT}

{f"## Conversation History\n{history}\n" if history else ""}Analyze the following question step by step:

Context:
{context}

Question: {message}

Provide a step-by-step reasoning process:"""
                                else:
                                    reasoning_prompt = f"""{SYSTEM_PROMPT}

{f"## Conversation History\n{history}\n" if history else ""}Analyze the following question step by step:

Question: {message}

Provide a step-by-step reasoning process:"""
                                
                                # Stream reasoning
                                full_reasoning = ""
                                async for chunk in reasoning_model.astream(reasoning_prompt):
                                    full_reasoning += chunk
                                    # Don't send reasoning content, just update status
                                
                                # Now get main model response with reasoning
                                main_model = orchestrator.llm_wrapper._multi_model_manager.models["main"]
                                
                                if chunks:
                                    main_prompt = f"""{SYSTEM_PROMPT}

{f"## Conversation History\n{history}\n" if history else ""}Based on the following reasoning and context, provide a clear and concise answer:

Reasoning:
{full_reasoning}

Context:
{context}

## Current Message
User: {message}

Assistant:"""
                                else:
                                    main_prompt = f"""{SYSTEM_PROMPT}

{f"## Conversation History\n{history}\n" if history else ""}Based on the following reasoning, provide a clear and concise answer:

Reasoning:
{full_reasoning}

## Current Message
User: {message}

Assistant:"""
                                
                                # Stream main response
                                full_response = ""
                                async for chunk in main_model.astream(main_prompt):
                                    full_response += chunk
                                    await manager.send_message(client_id, {
                                        "type": "stream_token",
                                        "content": chunk
                                    })
                                
                                # Send completion
                                await manager.send_message(client_id, {
                                    "type": "stream_end",
                                    "content": full_response
                                })
                                
                                # Add to conversation
                                orchestrator.conversation.add_message("assistant", full_response)
                                orchestrator._prune_history()
                            else:
                                # No reasoning model, use main
                                await stream_simple_response(websocket, client_id, message, orchestrator, use_reasoning=False, user_id=user_id)
                        else:
                            # Multi-model not available, fallback
                            await stream_simple_response(websocket, client_id, message, orchestrator, use_reasoning=False, user_id=user_id)
                            
                    except ValueError as e:
                        logger.warning(f"Reasoning mode not available: {str(e)}")
                        await stream_simple_response(websocket, client_id, message, orchestrator, use_reasoning=False, user_id=user_id)
                else:
                    # Simple mode with streaming
                    await stream_simple_response(
                        websocket, 
                        client_id, 
                        message, 
                        orchestrator,
                        use_reasoning=False,
                        user_id=user_id
                    )
            
            except Exception as e:
                logger.error(f"Error generating response: {str(e)}")
                await manager.send_message(client_id, {
                    "type": "error",
                    "content": f"Error: {str(e)}"
                })
    
    except WebSocketDisconnect:
        manager.disconnect(client_id)
        cleanup_client(client_id)
    
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        manager.disconnect(client_id)
        cleanup_client(client_id)


async def stream_simple_response(websocket: WebSocket, client_id: str, message: str, orchestrator, use_reasoning: bool = False, user_id: Optional[str] = None):
    """Stream a simple response token by token."""
    from ..rag.context_builder import ContextBuilder
    from ..llm.prompts import SYSTEM_PROMPT

    # Record user message in history (caller no longer pre-adds to avoid double-insertion)
    orchestrator.conversation.add_message("user", message)

    # Search RAG for context (scoped to this user's own documents)
    raw_chunks = orchestrator.rag_store.search_chunks(message, top_k=5, user_id=user_id)

    # --- Security: filter document chunks ---
    safe_chunks = []
    for chunk in raw_chunks:
        f = filter_document_chunk(chunk.content)
        if not f.blocked:
            chunk.content = f.content
            safe_chunks.append(chunk)

    # Get conversation history
    history = orchestrator._format_history(exclude_last_user=True)

    # --- Security: build secure delimited prompt ---
    context_builder = ContextBuilder()
    documents = context_builder.build_context(safe_chunks) if safe_chunks else ""
    prompt = build_secure_prompt(
        system=SYSTEM_PROMPT,
        user_query=message,
        documents=documents,
        history=history,
    )
    
    # Send start signal
    await manager.send_message(client_id, {
        "type": "stream_start"
    })
    
    try:
        # Check if multi-model is available and use appropriate model
        if orchestrator.llm_wrapper.is_multi_model and orchestrator.llm_wrapper._multi_model_manager:
            # Use multi-model manager
            if use_reasoning and "reasoning" in orchestrator.llm_wrapper._multi_model_manager.models:
                model_to_use = orchestrator.llm_wrapper._multi_model_manager.models["reasoning"]
                model_name = orchestrator.llm_wrapper.config.multi_model["reasoning"].model_name
                logger.info(f"WebSocket streaming using reasoning model: {model_name}")
            else:
                model_to_use = orchestrator.llm_wrapper._multi_model_manager.models["main"]
                model_name = orchestrator.llm_wrapper.config.multi_model["main"].model_name
                logger.info(f"WebSocket streaming using main model: {model_name}")
        else:
            # Fallback to single model
            model_to_use = orchestrator.llm_wrapper.get_llm()
            if hasattr(orchestrator.llm_wrapper.config, 'model_name'):
                model_name = orchestrator.llm_wrapper.config.model_name
                provider = orchestrator.llm_wrapper.config.provider
                logger.info(f"WebSocket streaming using LLM: {provider} - {model_name}")
            else:
                logger.info("WebSocket streaming using LLM")
        
        # Stream tokens using LangChain's streaming
        full_response = ""
        async for chunk in model_to_use.astream(prompt):
            full_response += chunk
            await manager.send_message(client_id, {
                "type": "stream_token",
                "content": chunk
            })
        
        # Send completion signal
        await manager.send_message(client_id, {
            "type": "stream_end",
            "content": full_response
        })
        
        # Add to conversation history
        orchestrator.conversation.add_message("assistant", full_response)
        orchestrator._prune_history()
        
    except Exception as e:
        logger.error(f"Streaming error: {str(e)}")
        await manager.send_message(client_id, {
            "type": "error",
            "content": f"Streaming error: {str(e)}"
        })
