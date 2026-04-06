from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict
import json
import asyncio
from ..core.logging_config import get_logger
from ..utils.reasoning_detector import detect_reasoning_needed

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


async def handle_chat_websocket(websocket: WebSocket, client_id: str, orchestrator):
    """Handle WebSocket chat connection with streaming."""
    await manager.connect(websocket, client_id)
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()
            message = data.get("message", "")
            conversation_id = data.get("conversation_id", "default")
            use_agent = data.get("use_agent", False)
            use_reasoning = data.get("use_reasoning", False)
            
            # Auto-detect reasoning if not explicitly set
            if not use_reasoning and detect_reasoning_needed(message):
                use_reasoning = True
                logger.info(f"Auto-detected reasoning needed for: {message[:50]}...")
            
            if not message:
                continue
            
            logger.info(f"WebSocket message from {client_id}: {message} (reasoning={use_reasoning})")
            
            # Start or resume conversation
            if orchestrator.conversation is None or orchestrator.conversation.conversation_id != conversation_id:
                orchestrator.start_conversation(conversation_id)
            
            # Add user message
            orchestrator.conversation.add_message("user", message)
            
            # Send acknowledgment
            await manager.send_message(client_id, {
                "type": "user_message",
                "content": message
            })
            
            try:
                # Generate response with streaming
                if use_agent:
                    # For agent mode, we can't easily stream, so send complete response
                    logger.info(f"WebSocket agent mode activated for: {message[:50]}...")
                    response = orchestrator.chat(message)
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
                                # Notify reasoning phase
                                await manager.send_message(client_id, {
                                    "type": "reasoning",
                                    "content": ""
                                })
                                
                                # Get reasoning from reasoning model
                                reasoning_model = orchestrator.llm_wrapper._multi_model_manager.models["reasoning"]
                                chunks = orchestrator.rag_store.search_chunks(message, top_k=5)
                                
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
                                    await asyncio.sleep(0.01)
                                
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
                                await stream_simple_response(websocket, client_id, message, orchestrator, use_reasoning=False)
                        else:
                            # Multi-model not available, fallback
                            await stream_simple_response(websocket, client_id, message, orchestrator, use_reasoning=False)
                            
                    except ValueError as e:
                        logger.warning(f"Reasoning mode not available: {str(e)}")
                        await stream_simple_response(websocket, client_id, message, orchestrator, use_reasoning=False)
                else:
                    # Simple mode with streaming
                    await stream_simple_response(
                        websocket, 
                        client_id, 
                        message, 
                        orchestrator,
                        use_reasoning=False
                    )
            
            except Exception as e:
                logger.error(f"Error generating response: {str(e)}")
                await manager.send_message(client_id, {
                    "type": "error",
                    "content": f"Error: {str(e)}"
                })
    
    except WebSocketDisconnect:
        manager.disconnect(client_id)
        logger.info(f"Client {client_id} disconnected")
    
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        manager.disconnect(client_id)


async def stream_simple_response(websocket: WebSocket, client_id: str, message: str, orchestrator, use_reasoning: bool = False):
    """Stream a simple response token by token."""
    from ..rag.context_builder import ContextBuilder
    from ..llm.prompts import SYSTEM_PROMPT
    
    # Search RAG for context
    chunks = orchestrator.rag_store.search_chunks(message, top_k=5)
    
    # Get conversation history
    history = orchestrator._format_history(exclude_last_user=True)
    
    # Build prompt with context and history
    context_builder = ContextBuilder()
    if chunks:
        context = context_builder.build_context(chunks)
        prompt = f"""{SYSTEM_PROMPT}

{f"## Conversation History\n{history}\n" if history else ""}## Retrieved Context
Use the following context to answer the question. If the context doesn't contain relevant information, answer based on your general knowledge.

{context}

## Current Message
User: {message}

Assistant:"""
    else:
        prompt = f"""{SYSTEM_PROMPT}

{f"## Conversation History\n{history}\n" if history else ""}## Current Message
User: {message}

Assistant:"""
    
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
            await asyncio.sleep(0.01)  # Small delay for smooth streaming
        
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
