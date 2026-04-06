from fastapi import FastAPI, HTTPException, WebSocket, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from pathlib import Path
import uvicorn
import uuid

from ..config.loader import load_config
from ..core.logging_config import setup_logging, get_logger
from ..llm.langchain_wrapper import LangChainLLM
from ..rag.page_index_store import PageIndexStore
from ..rag.chunker import DocumentChunker
from ..search.search_service import SearchService
from ..chat.orchestrator import ChatOrchestrator
from ..ingestion.loaders import DocumentLoader
from ..ingestion.pipeline import IngestionPipeline
from .websocket import handle_chat_websocket
from .analytics_routes import router as analytics_router
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
    "ingestion_pipeline": None
}

# Create FastAPI app
app = FastAPI(
    title="RAG Chatbot API",
    description="Chatbot with RAG and internet search capabilities",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include analytics router
app.include_router(analytics_router)


@app.on_event("startup")
async def startup_event():
    """Initialize the application on startup."""
    logger.info("Starting RAG Chatbot API...")
    
    # Load configuration
    config = load_config()
    app_state["config"] = config
    
    # Setup logging
    setup_logging(config.logging)
    
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
    
    # Initialize chat orchestrator
    orchestrator = ChatOrchestrator(
        llm_wrapper=llm_wrapper,
        rag_store=rag_store,
        search_service=search_service,
        max_history=config.conversation.max_history
    )
    app_state["orchestrator"] = orchestrator
    
    # Initialize chunker and ingestion pipeline
    chunker = DocumentChunker(config.rag)
    app_state["chunker"] = chunker
    
    ingestion_pipeline = IngestionPipeline(rag_store, chunker)
    app_state["ingestion_pipeline"] = ingestion_pipeline
    
    logger.info("RAG Chatbot API started successfully")


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
            response = orchestrator.chat(request.message)
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
    
    # Check file extension
    filename = file.filename
    if not filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ['.txt', '.pdf', '.md', '.markdown']:
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported file type: {ext}. Supported: .txt, .pdf, .md"
        )
    
    # Ensure data/documents directory exists
    documents_dir = Path("data/documents")
    documents_dir.mkdir(parents=True, exist_ok=True)
    
    # Create destination path
    dest_path = documents_dir / filename
    
    # Handle duplicate filenames
    counter = 1
    base_name = os.path.splitext(filename)[0]
    while dest_path.exists():
        new_filename = f"{base_name}_{counter}{ext}"
        dest_path = documents_dir / new_filename
        counter += 1
    
    try:
        # Save uploaded file to data/documents
        content = await file.read()
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


@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """WebSocket endpoint for streaming chat."""
    orchestrator = app_state.get("orchestrator")
    
    if orchestrator is None:
        await websocket.close(code=1011, reason="Service not initialized")
        return
    
    await handle_chat_websocket(websocket, client_id, orchestrator)


def run_server(host: str = "localhost", port: int = 8000):
    """Run the FastAPI server."""
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
