from fastapi import FastAPI, HTTPException, WebSocket, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from pathlib import Path
import uvicorn
import uuid

from ..config.loader import load_config
from ..core.logging_config import setup_logging, get_logger
from ..security.rate_limit_middleware import RateLimitMiddleware
from ..security.security_headers_middleware import SecurityHeadersMiddleware
from ..security.audit_logger import init_audit_logger, get_audit_logger
from ..security.file_validator import validate_upload
from ..llm.langchain_wrapper import LangChainLLM
from ..rag.page_index_store import PageIndexStore
from ..rag.chunker import DocumentChunker
from ..search.search_service import SearchService
from ..chat.orchestrator import ChatOrchestrator
from ..ingestion.loaders import DocumentLoader
from ..ingestion.pipeline import IngestionPipeline
from .websocket import handle_chat_websocket
from .analytics_routes import router as analytics_router
from .auth_routes import router as auth_router, init_auth_routes
from .news_routes import router as news_router
from .db_routes import router as db_router
from ..auth.user_store import UserStore
from ..auth.dependencies import set_user_store
from ..memory.memory_store import MemoryStore
from ..memory.memory_manager import MemoryManager
from ..memory.models import MemoryType
from ..tasks.mcp_manager import MCPManager
from ..tasks.task_engine import TaskEngine
from ..learning.feedback_collector import FeedbackCollector
from ..learning.learning_engine import LearningEngine
from ..proactive.proactive_engine import ProactiveEngine
from ..mcp.tools import set_dependencies as set_mcp_dependencies
from ..mcp.server import start_mcp_server
from ..mcp_client.server_store import ServerConfigStore as MCPClientStore
from ..mcp_client.manager import MCPClientManager
from .mcp_client_routes import router as mcp_client_router
import asyncio
import tempfile
import os

logger = get_logger(__name__)

# Request/Response models
class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = "default"
    use_agent: bool = False
    auto_web_search: bool = True 

class ChatResponse(BaseModel):
    response: str
    conversation_id: str

class DocumentInfo(BaseModel):
    doc_id: str
    filename: str
    file_type: str
    file_size: int
    num_chunks: int

class HealthResponse(BaseModel):
    status: str
    num_documents: int
    num_chunks: int

# Global state
app_state = {
    "config": None,
    "orchestrator": None,
    "rag_store": None,
    "chunker": None,
    "ingestion_pipeline": None,
    "memory_store": None,
    "memory_manager": None,
    "task_engine": None,
    "feedback_collector": None,
    "learning_engine": None,
    "proactive_engine": None,
    "proactive_task": None,
    "mcp_client_store": None,
    "mcp_client_manager": None,
}

# Create FastAPI app
app = FastAPI(
    title="RAG Chatbot API",
    description="Chatbot with RAG and internet search capabilities",
    version="1.0.0"
)

# Load config early for CORS setup (re-loaded fully during startup)
try:
    _early_config = load_config()
    _cors_origins = _early_config.server.cors_origins
except Exception:
    _cors_origins = ["http://localhost:3000", "http://localhost:5173"]

# Add security middleware (order matters: outermost runs first)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware, enabled=True)

# Add CORS middleware — origins sourced from config, not hardcoded
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(analytics_router)
app.include_router(auth_router)
app.include_router(news_router)
app.include_router(db_router)
app.include_router(mcp_client_router)


@app.on_event("startup")
async def startup_event():
    """Initialize the application on startup."""
    logger.info("Starting RAG Chatbot API...")
    
    # Load configuration
    config = load_config()
    app_state["config"] = config
    
    # Setup logging
    setup_logging(config.logging)

    # Initialise audit logger with configured path
    init_audit_logger(config.security.audit_log_path)

    # Initialise auth system (always register the store; endpoints exist even when disabled)
    user_store = UserStore(config.auth.db_path)
    set_user_store(user_store)
    init_auth_routes(user_store)
    if config.auth.enabled:
        logger.info("Authentication system enabled")
    else:
        logger.info("Authentication system initialised (disabled — set auth.enabled=true to protect endpoints)")
    
    # Initialize RAG store
    rag_store = PageIndexStore(config.rag.index_path)
    rag_store.load()
    app_state["rag_store"] = rag_store
    
    logger.info(f"Loaded {len(rag_store.list_documents())} documents from index")
    
    # Initialize LLM
    llm_wrapper = LangChainLLM(config.llm)
    llm_wrapper.initialize()
    
    # Initialize search service
    search_service = SearchService(config.search)
    
    # Initialize memory system
    memory_store = MemoryStore(config.memory.store_path)
    memory_manager = MemoryManager(memory_store) if config.memory.enabled else None
    app_state["memory_store"] = memory_store
    app_state["memory_manager"] = memory_manager
    if config.memory.enabled:
        logger.info("Memory system initialized")

    # Initialise MCP client store and manager (before orchestrator so tools are available at start)
    mcp_client_store = MCPClientStore(config.mcp_client.store_path)
    app_state["mcp_client_store"] = mcp_client_store
    if config.mcp_clients:
        migrated = mcp_client_store.migrate_from_yaml(config.mcp_clients)
        if migrated:
            logger.info(f"Migrated {migrated} MCP client(s) from config.yaml to DB")

    mcp_client_manager = MCPClientManager(mcp_client_store)
    app_state["mcp_client_manager"] = mcp_client_manager
    try:
        await mcp_client_manager.initialize_all()
    except Exception as e:
        logger.warning(f"MCP client manager init warning: {e}")

    # Initialize chat orchestrator
    orchestrator = ChatOrchestrator(
        llm_wrapper=llm_wrapper,
        rag_store=rag_store,
        search_service=search_service,
        max_history=config.conversation.max_history,
        memory_manager=memory_manager,
        mcp_client_manager=mcp_client_manager,
    )
    app_state["orchestrator"] = orchestrator

    # Register tools-changed callback so agent + SSE MCP server rebuild when servers connect/disconnect
    def _on_mcp_tools_changed():
        orchestrator.rebuild_tools()
        # Re-inject mcp_client_manager so SSE server's get_tools() picks up new tools instantly
        from ..mcp.tools import set_dependencies as _set_mcp_deps
        _set_mcp_deps(
            rag_store=rag_store,
            search_service=search_service,
            orchestrator=orchestrator,
            task_engine=app_state.get("task_engine"),
            news_service=app_state.get("news_service"),
            mcp_client_manager=mcp_client_manager,
        )
    mcp_client_manager.set_tools_changed_callback(_on_mcp_tools_changed)
    
    # Initialize chunker and ingestion pipeline
    chunker = DocumentChunker(config.rag)
    app_state["chunker"] = chunker
    
    ingestion_pipeline = IngestionPipeline(rag_store, chunker)
    app_state["ingestion_pipeline"] = ingestion_pipeline

    # Initialize task engine
    if config.tasks.enabled:
        mcp_manager = MCPManager(config.tasks.task_clients or [])
        if config.tasks.task_clients:
            await mcp_manager.initialize_clients()
        task_engine = TaskEngine(mcp_manager)
        app_state["task_engine"] = task_engine
        logger.info("Task engine initialized")

    # Initialize learning system
    feedback_collector = FeedbackCollector(config.memory.store_path)
    learning_engine = LearningEngine(memory_store)
    app_state["feedback_collector"] = feedback_collector
    app_state["learning_engine"] = learning_engine
    if config.learning.enabled:
        logger.info("Learning system initialized")

    # Initialize proactive engine
    if config.proactive.enabled:
        from ..proactive.context_analyzer import ContextAnalyzer
        from ..proactive.content_generator import ContentGenerator
        from ..proactive.notification_service import NotificationService
        context_analyzer = ContextAnalyzer(memory_store)
        proactive_engine = ProactiveEngine(
            context_analyzer=context_analyzer,
            content_generator=ContentGenerator(),
            notification_service=NotificationService(),
            memory_store=memory_store,
            briefing_hour=config.proactive.briefing_hour
        )
        app_state["proactive_engine"] = proactive_engine
        task = asyncio.create_task(
            proactive_engine.start_background_loop(config.proactive.cycle_interval_minutes)
        )
        app_state["proactive_task"] = task
        logger.info("Proactive engine started")

    # Start MCP SSE server
    if config.mcp_server.enabled:
        asyncio.create_task(
            start_mcp_server(host="0.0.0.0", port=config.mcp_server.port)
        )
        logger.info(f"MCP SSE server starting on port {config.mcp_server.port}")

    # Initialise news service (optional — set news.enabled=true in config.yaml)
    if config.news.enabled:
        try:
            from ..news.keyword_store import KeywordStore as _KWStore
            from ..news.article_store import ArticleStore as _ArtStore
            from ..news.fetcher import NewsFetcher as _Fetcher
            from ..news.processor import ArticleProcessor as _Proc
            from ..news.summariser import Summariser as _Sum
            from ..news.scheduler import NewsScheduler as _Sched
            from ..news.news_service import NewsService as _NS

            kw_store = _KWStore(config.news.db_path)
            art_store = _ArtStore(config.news.db_path)
            fetcher = _Fetcher(region=config.news.region)  # wt-wt = worldwide/any language

            rag_store_for_news = rag_store if config.news.ingest_into_rag else None
            processor = _Proc(
                article_store=art_store,
                rag_store=rag_store_for_news,
                max_content_chars=config.news.max_content_chars,
                ingest_into_rag=config.news.ingest_into_rag,
            )
            summariser = _Sum(llm_wrapper=llm_wrapper, max_content_chars=config.news.max_content_chars)

            _holder = [None]
            scheduler = _Sched(
                run_for_keyword_fn=lambda kid: _holder[0].run_for_keyword(kid),
                run_cleanup_fn=lambda: _holder[0]._retention_cleanup(),
                cleanup_interval_hours=config.news.cleanup_interval_hours,
            )
            news_svc = _NS(
                keyword_store=kw_store,
                article_store=art_store,
                fetcher=fetcher,
                processor=processor,
                summariser=summariser,
                scheduler=scheduler,
                summarise_on_fetch=config.news.summarise_on_fetch,
                retention_days=config.news.retention_days,
                rag_store=rag_store_for_news,
            )
            _holder[0] = news_svc
            cleanup = news_svc.run_startup_cleanup()
            news_svc.start()
            app_state["news_service"] = news_svc
            logger.info(
                f"News service started (retention cleanup removed {cleanup.deleted} expired articles)"
            )
        except Exception as e:
            logger.error(f"News service failed to initialise: {e}")
    else:
        logger.info("News service disabled (set news.enabled=true to activate)")

    # Inject dependencies into MCP tool handlers — done last so news + MCP client are ready
    set_mcp_dependencies(
        rag_store=rag_store,
        search_service=search_service,
        orchestrator=orchestrator,
        task_engine=app_state.get("task_engine"),
        news_service=app_state.get("news_service"),
        mcp_client_manager=app_state.get("mcp_client_manager"),
    )

    logger.info("RAG Chatbot API started successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Graceful shutdown."""
    news_svc = app_state.get("news_service")
    if news_svc:
        news_svc.stop()
        logger.info("News service stopped")

    mcp_mgr = app_state.get("mcp_client_manager")
    if mcp_mgr:
        await mcp_mgr.shutdown()
        logger.info("MCP client manager shut down")


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    rag_store = app_state.get("rag_store")
    
    if rag_store is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    stats = rag_store.get_stats()
    
    return HealthResponse(
        status="healthy",
        num_documents=stats["num_documents"],
        num_chunks=stats["num_chunks"]
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Chat endpoint."""
    orchestrator = app_state.get("orchestrator")
    
    if orchestrator is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        # Start or resume conversation
        if orchestrator.conversation is None or orchestrator.conversation.conversation_id != request.conversation_id:
            orchestrator.start_conversation(request.conversation_id)
        
        # Generate response
        if request.use_agent:
            response = await orchestrator.achat(request.message)
        else:
            response = orchestrator.chat_simple(request.message)
        
        return ChatResponse(
            response=response,
            conversation_id=request.conversation_id
        )
    
    except Exception as e:
        logger.error(f"Chat error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/history/{conversation_id}")
async def get_history(conversation_id: str):
    """Get conversation history."""
    orchestrator = app_state.get("orchestrator")
    
    if orchestrator is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    if orchestrator.conversation is None or orchestrator.conversation.conversation_id != conversation_id:
        return {"messages": []}
    
    return {"messages": orchestrator.get_conversation_history()}


@app.delete("/history/{conversation_id}")
async def clear_history(conversation_id: str):
    """Clear conversation history."""
    orchestrator = app_state.get("orchestrator")
    
    if orchestrator is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    if orchestrator.conversation and orchestrator.conversation.conversation_id == conversation_id:
        orchestrator.clear_conversation()
    
    return {"status": "cleared"}


@app.get("/documents", response_model=List[DocumentInfo])
async def list_documents():
    """List all indexed documents."""
    rag_store = app_state.get("rag_store")
    
    if rag_store is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    documents = rag_store.list_documents()
    
    return [
        DocumentInfo(
            doc_id=doc.doc_id,
            filename=doc.filename,
            file_type=doc.file_type,
            file_size=doc.file_size,
            num_chunks=len(doc.chunks)
        )
        for doc in documents
    ]


@app.get("/documents/{doc_id}/summarize")
async def summarize_document(doc_id: str):
    """Generate a summary of a document using LLM."""
    rag_store = app_state.get("rag_store")
    orchestrator = app_state.get("orchestrator")
    
    if rag_store is None or orchestrator is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    # Get document
    doc = rag_store.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    try:
        # Collect content from chunks (limit to first 4000 words)
        content_parts = []
        word_count = 0
        for chunk in doc.chunks:
            chunk_words = chunk.content.split()
            if word_count + len(chunk_words) > 4000:
                remaining = 4000 - word_count
                content_parts.append(' '.join(chunk_words[:remaining]))
                break
            content_parts.append(chunk.content)
            word_count += len(chunk_words)
        
        content = '\n\n'.join(content_parts)
        
        # Create summarization prompt
        prompt = f"""Analyze and summarize the following document. You MUST use proper markdown formatting in your response.

Document: {doc.filename}

Content:
{content}

Please format your response EXACTLY as follows using markdown:

## Summary

Write 2-3 paragraphs summarizing the key information. Use **bold** for important terms, *italic* for emphasis, and proper paragraph breaks.

## Key Topics

- First main topic or theme
- Second main topic or theme
- Third main topic or theme
- (Continue with 5-10 topics total)

## Keywords

keyword1, keyword2, keyword3, keyword4, keyword5, keyword6, keyword7, keyword8, keyword9, keyword10

IMPORTANT: Use proper markdown syntax including headings (##), bullet points (-), **bold**, and *italic* formatting."""

        # Get LLM response
        logger.info(f"Generating summary for document: {doc.filename}")
        # Start a temporary conversation for summarization
        orchestrator.start_conversation(f"summarize_{doc_id}")
        response = orchestrator.chat_simple(prompt)
        
        # Extract keywords from response
        import re
        keywords_list = []
        keywords_match = re.search(r'## Keywords\s*\n(.+?)(?:\n\n|\Z)', response, re.DOTALL)
        if keywords_match:
            keywords_text = keywords_match.group(1).strip()
            keywords_list = [kw.strip() for kw in keywords_text.split(',')][:15]
        
        return {
            "status": "success",
            "doc_id": doc_id,
            "summary": {
                "filename": doc.filename,
                "file_type": doc.file_type,
                "num_chunks": len(doc.chunks),
                "preview": response,
                "keywords": [{"word": kw, "frequency": 0} for kw in keywords_list]
            }
        }
    
    except Exception as e:
        logger.error(f"Error summarizing document: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/documents/{doc_id}")
async def delete_document(doc_id: str):
    """Delete a document from the index and remove the physical file."""
    rag_store = app_state.get("rag_store")
    config = app_state.get("config")
    
    if rag_store is None or config is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    # Get document info before deleting
    doc = rag_store.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Delete from index
    success = rag_store.delete_document(doc_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Delete physical file if it exists in data/documents
    try:
        file_path = Path(doc.source)
        if file_path.exists() and "data/documents" in str(file_path):
            file_path.unlink()
            logger.info(f"Deleted physical file: {file_path}")
    except Exception as e:
        logger.warning(f"Could not delete physical file: {str(e)}")
    
    # Save the updated index
    rag_store.save()
    
    return {"status": "deleted", "doc_id": doc_id, "filename": doc.filename}


@app.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    """Upload and ingest a document. Saves to data/documents folder and chunks immediately."""
    ingestion_pipeline = app_state.get("ingestion_pipeline")
    rag_store = app_state.get("rag_store")
    config = app_state.get("config")
    
    if ingestion_pipeline is None or rag_store is None or config is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    filename = file.filename
    if not filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    content = await file.read()

    # --- Security: magic-byte + extension + size validation ---
    is_valid, val_error = validate_upload(filename, content)
    if not is_valid:
        get_audit_logger().upload_blocked(ip="unknown", filename=filename, reason=val_error)
        raise HTTPException(status_code=400, detail=val_error)

    ext = os.path.splitext(filename)[1].lower()
    
    # Ensure data/documents directory exists
    documents_dir = Path("data/documents")
    documents_dir.mkdir(parents=True, exist_ok=True)
    
    # Sanitize filename — strip any directory components to prevent path traversal
    safe_filename = Path(filename).name
    dest_path = (documents_dir / safe_filename).resolve()
    # Verify resolved path stays within documents_dir
    if not str(dest_path).startswith(str(documents_dir.resolve())):
        get_audit_logger().path_traversal_attempt(ip="unknown", filename=filename)
        raise HTTPException(status_code=400, detail="Invalid filename")

    # Handle duplicate filenames
    counter = 1
    base_name = os.path.splitext(safe_filename)[0]
    while dest_path.exists():
        new_filename = f"{base_name}_{counter}{ext}"
        dest_path = (documents_dir / new_filename).resolve()
        counter += 1
    
    try:
        # Save uploaded file to data/documents
        with open(dest_path, 'wb') as f:
            f.write(content)
        
        logger.info(f"Saved uploaded file to: {dest_path}")
        
        # Ingest the document (this will chunk it and add to index)
        doc = ingestion_pipeline.ingest_file(str(dest_path))
        
        # Save the index
        rag_store.save()
        
        return {
            "status": "success",
            "doc_id": doc.doc_id,
            "filename": doc.filename,
            "num_chunks": len(doc.chunks),
            "file_path": str(dest_path)
        }
    
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        # Clean up saved file if ingestion failed
        if dest_path.exists():
            try:
                dest_path.unlink()
                logger.info(f"Cleaned up file after failed ingestion: {dest_path}")
            except Exception as cleanup_error:
                logger.warning(f"Could not clean up file: {cleanup_error}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat-upload")
async def chat_upload(file: UploadFile = File(...), message: str = ""):
    """Upload a file in chat context. Ingests the file and returns its doc_id and extracted content summary
    so the frontend can send a follow-up chat message referencing the file."""
    ingestion_pipeline = app_state.get("ingestion_pipeline")
    rag_store = app_state.get("rag_store")
    orchestrator = app_state.get("orchestrator")
    
    if ingestion_pipeline is None or rag_store is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    filename = file.filename
    if not filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    content_bytes = await file.read()

    # --- Security: magic-byte + extension + size validation ---
    is_valid_cu, val_error_cu = validate_upload(filename, content_bytes)
    if not is_valid_cu:
        get_audit_logger().upload_blocked(ip="unknown", filename=filename, reason=val_error_cu)
        raise HTTPException(status_code=400, detail=val_error_cu)

    ext = os.path.splitext(filename)[1].lower()
    
    # Save to data/documents
    documents_dir = Path("data/documents")
    documents_dir.mkdir(parents=True, exist_ok=True)
    safe_filename_cu = Path(filename).name
    dest_path = (documents_dir / safe_filename_cu).resolve()
    if not str(dest_path).startswith(str(documents_dir.resolve())):
        get_audit_logger().path_traversal_attempt(ip="unknown", filename=filename)
        raise HTTPException(status_code=400, detail="Invalid filename")
    counter = 1
    base_name = os.path.splitext(safe_filename_cu)[0]
    while dest_path.exists():
        new_filename = f"{base_name}_{counter}{ext}"
        dest_path = (documents_dir / new_filename).resolve()
        counter += 1
    
    try:
        with open(dest_path, 'wb') as f:
            f.write(content_bytes)
        
        logger.info(f"Chat-upload saved file to: {dest_path}")
        
        # Ingest the file
        doc = ingestion_pipeline.ingest_file(str(dest_path))
        rag_store.save()
        
        # Build a content preview (first 500 chars)
        preview = doc.content[:500] + ("..." if len(doc.content) > 500 else "")
        
        return {
            "status": "success",
            "doc_id": doc.doc_id,
            "filename": doc.filename,
            "file_type": doc.file_type,
            "file_size": doc.file_size,
            "num_chunks": len(doc.chunks),
            "preview": preview
        }
    
    except Exception as e:
        error_msg = str(e)
        
        # Handle duplicate document gracefully
        if "already exists" in error_msg.lower() or "duplicate" in error_msg.lower():
            logger.warning(f"Chat-upload: Document already exists, returning existing doc: {filename}")
            # Clean up the newly saved file since we're using the existing one
            if dest_path.exists():
                try:
                    dest_path.unlink()
                except Exception:
                    pass
            
            # Find and return the existing document
            existing_doc = next((d for d in rag_store.list_documents() if d.filename == filename), None)
            if existing_doc:
                preview = existing_doc.content[:500] + ("..." if len(existing_doc.content) > 500 else "")
                return {
                    "status": "success",
                    "doc_id": existing_doc.doc_id,
                    "filename": existing_doc.filename,
                    "file_type": existing_doc.file_type,
                    "file_size": existing_doc.file_size,
                    "num_chunks": len(existing_doc.chunks),
                    "preview": preview,
                    "note": "Document was already uploaded previously"
                }
        
        # For other errors, clean up and raise
        logger.error(f"Chat-upload error: {error_msg}")
        if dest_path.exists():
            try:
                dest_path.unlink()
            except Exception:
                pass
        raise HTTPException(status_code=500, detail=error_msg)


@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """WebSocket endpoint for streaming chat."""
    orchestrator = app_state.get("orchestrator")
    
    if orchestrator is None:
        await websocket.close(code=1011, reason="Service not initialized")
        return
    
    await handle_chat_websocket(websocket, client_id, orchestrator)


# ── Memory Endpoints ────────────────────────────────────────────────────────

class MemoryStoreRequest(BaseModel):
    content: str
    memory_type: str = "fact"
    metadata: Optional[Dict[str, Any]] = None

class PreferencesRequest(BaseModel):
    preferences: Dict[str, Any]

class LearningGoalsRequest(BaseModel):
    goals: List[str]

@app.post("/api/memory/store")
async def store_memory(request: MemoryStoreRequest):
    memory_manager: Optional[MemoryManager] = app_state.get("memory_manager")
    if memory_manager is None:
        raise HTTPException(status_code=503, detail="Memory system not enabled")
    try:
        mem_type = MemoryType(request.memory_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid memory_type: {request.memory_type}")
    memory_id = memory_manager.add_context(request.content, mem_type, request.metadata)
    return {"memory_id": memory_id, "status": "stored"}

@app.get("/api/memory/search")
async def search_memories(q: str, limit: int = 10):
    memory_store: Optional[MemoryStore] = app_state.get("memory_store")
    if memory_store is None:
        raise HTTPException(status_code=503, detail="Memory system not enabled")
    memories = memory_store.retrieve_memories(q, limit=limit)
    return {"memories": [m.model_dump() for m in memories], "count": len(memories)}

@app.put("/api/memory/preferences")
async def update_preferences(request: PreferencesRequest):
    memory_manager: Optional[MemoryManager] = app_state.get("memory_manager")
    if memory_manager is None:
        raise HTTPException(status_code=503, detail="Memory system not enabled")
    memory_manager.update_preferences(request.preferences)
    return {"status": "updated"}

@app.get("/api/memory/profile")
async def get_profile():
    memory_manager: Optional[MemoryManager] = app_state.get("memory_manager")
    if memory_manager is None:
        raise HTTPException(status_code=503, detail="Memory system not enabled")
    return memory_manager.get_user_profile()

@app.put("/api/memory/goals")
async def set_learning_goals(request: LearningGoalsRequest):
    memory_manager: Optional[MemoryManager] = app_state.get("memory_manager")
    if memory_manager is None:
        raise HTTPException(status_code=503, detail="Memory system not enabled")
    memory_manager.set_learning_goals(request.goals)
    return {"status": "updated", "goals": request.goals}


# ── Task Endpoints ───────────────────────────────────────────────────────────

class TaskRequest(BaseModel):
    request: str
    context: Optional[Dict[str, Any]] = None

@app.post("/api/tasks/execute")
async def execute_task(request: TaskRequest):
    task_engine: Optional[TaskEngine] = app_state.get("task_engine")
    if task_engine is None:
        raise HTTPException(status_code=503, detail="Task execution not enabled. Set tasks.enabled=true in config.")
    result = await task_engine.execute_task(request.request, request.context)
    return {"success": result.success, "summary": result.summary, "details": result.details}


# ── Learning / Feedback Endpoints ────────────────────────────────────────────

class FeedbackRequest(BaseModel):
    message_id: str
    rating: str  # "thumbs_up" or "thumbs_down"
    comment: Optional[str] = ""
    topic: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class CorrectionRequest(BaseModel):
    message_id: str
    original_response: str
    corrected_response: str
    topic: Optional[str] = None

@app.post("/api/feedback")
async def submit_feedback(request: FeedbackRequest):
    feedback_collector: Optional[FeedbackCollector] = app_state.get("feedback_collector")
    learning_engine: Optional[LearningEngine] = app_state.get("learning_engine")
    if feedback_collector is None:
        raise HTTPException(status_code=503, detail="Learning system not initialized")
    feedback = await feedback_collector.collect_feedback("explicit", {
        "message_id": request.message_id,
        "rating": request.rating,
        "comment": request.comment,
        "metadata": {"topic": request.topic, **(request.metadata or {})}
    })
    if learning_engine:
        await learning_engine.process_feedback(feedback, topic=request.topic)
    return {"status": "received", "feedback_id": feedback.id}

@app.post("/api/feedback/correction")
async def submit_correction(request: CorrectionRequest):
    feedback_collector: Optional[FeedbackCollector] = app_state.get("feedback_collector")
    learning_engine: Optional[LearningEngine] = app_state.get("learning_engine")
    if feedback_collector is None:
        raise HTTPException(status_code=503, detail="Learning system not initialized")
    feedback = await feedback_collector.collect_feedback("correction", {
        "message_id": request.message_id,
        "original_response": request.original_response,
        "corrected_response": request.corrected_response,
        "metadata": {"topic": request.topic}
    })
    if learning_engine:
        await learning_engine.process_feedback(feedback, topic=request.topic)
    return {"status": "received", "feedback_id": feedback.id}

@app.get("/api/learning/summary")
async def get_learning_summary():
    learning_engine: Optional[LearningEngine] = app_state.get("learning_engine")
    if learning_engine is None:
        raise HTTPException(status_code=503, detail="Learning system not initialized")
    return learning_engine.get_learning_summary()

@app.get("/api/feedback/stats")
async def get_feedback_stats():
    feedback_collector: Optional[FeedbackCollector] = app_state.get("feedback_collector")
    if feedback_collector is None:
        raise HTTPException(status_code=503, detail="Learning system not initialized")
    return feedback_collector.get_stats()


# ── Proactive Endpoints ──────────────────────────────────────────────────────

@app.post("/api/proactive/briefing")
async def trigger_briefing():
    proactive_engine: Optional[ProactiveEngine] = app_state.get("proactive_engine")
    if proactive_engine is None:
        raise HTTPException(status_code=503, detail="Proactive engine not enabled. Set proactive.enabled=true in config.")
    await proactive_engine.run_proactive_cycle()
    return {"status": "briefing delivered"}

@app.get("/api/proactive/due-reviews")
async def get_due_reviews():
    proactive_engine: Optional[ProactiveEngine] = app_state.get("proactive_engine")
    if proactive_engine is None:
        raise HTTPException(status_code=503, detail="Proactive engine not enabled")
    due = proactive_engine.scheduler.get_due_reviews()
    return {"due_reviews": [{"topic": r.topic, "mastery": r.mastery} for r in due]}


def run_server(host: str = "localhost", port: int = 8000):
    """Run the FastAPI server."""
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
