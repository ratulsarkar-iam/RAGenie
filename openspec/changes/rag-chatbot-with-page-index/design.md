## Context

Building a personal RAG-powered chatbot for Mac M3 (16GB RAM) that combines internet search with custom document knowledge. The system must be configuration-driven to allow easy switching between models and future migration from page-based indexing to vector databases. Current state: greenfield project with no existing chatbot infrastructure.

**Constraints:**
- Mac M3 chip with 16GB RAM limits model size (prefer quantized models, 7B parameters or smaller)
- Personal use only, single-user deployment on localhost
- Must support both web and mobile browser interfaces
- Page-based indexing initially, but architecture must support vector DB migration

**Stakeholders:**
- Single user (personal productivity tool)

## Goals / Non-Goals

**Goals:**
- Conversational interface accessible from web and mobile browsers
- Integrate HuggingFace models with LangChain orchestration
- Real-time internet search for current information
- RAG with page-based document indexing
- Configuration file for all system parameters (models, search, indexing, MCP servers)
- Extensible architecture for future vector DB integration
- MCP client integration to access external tools from configured MCP servers
- MCP server mode to expose RAG and search capabilities to external LLM clients
- Optimized performance for M3 hardware

**Non-Goals:**
- Multi-user support or authentication
- Cloud deployment or distributed architecture
- Fine-tuning custom models
- Production-grade monitoring or observability
- Multi-language support (English only initially)

## Decisions

### 1. Architecture Pattern: Modular Service Layer
**Decision:** Use a modular Python backend with separate services for LLM, RAG, search, and chat orchestration.

**Rationale:** 
- Enables independent testing and future replacement of components (e.g., swapping page index for vector DB)
- Clear separation of concerns between retrieval, generation, and search
- Easier to configure and maintain

**Alternatives Considered:**
- Monolithic approach: Rejected due to difficulty in swapping components
- Microservices: Overkill for single-user local deployment

### 2. LLM Selection: HuggingFace Transformers with Quantization
**Decision:** Use HuggingFace Transformers library with 4-bit quantization (bitsandbytes) for models like Mistral-7B-Instruct or Llama-2-7B-Chat.

**Rationale:**
- Quantized 7B models fit comfortably in 16GB RAM (~4-5GB VRAM)
- HuggingFace provides extensive model ecosystem
- Transformers library integrates seamlessly with LangChain
- M3 GPU acceleration via MPS (Metal Performance Shaders)

**Alternatives Considered:**
- OpenAI API: Rejected to avoid external dependencies and costs
- Larger models (13B+): Exceed memory constraints even with quantization
- GGUF/llama.cpp: Considered but Transformers offers better LangChain integration

### 3. Web Framework: FastAPI + WebSockets
**Decision:** FastAPI backend with WebSocket support for streaming responses, React frontend with responsive design.

**Rationale:**
- FastAPI provides async support for non-blocking LLM inference
- WebSockets enable real-time streaming of generated tokens
- React with Tailwind CSS ensures responsive mobile/desktop UI
- Simple deployment on localhost

**Alternatives Considered:**
- Gradio/Streamlit: Less control over UI customization and mobile optimization
- Flask: Lacks native async and WebSocket support

### 4. RAG Indexing: Page-Based with Abstract Storage Interface
**Decision:** Implement page-based indexing using simple JSON storage with an abstract `DocumentStore` interface that can be swapped for vector databases.

**Rationale:**
- Page-based indexing is simpler and faster for small document sets
- Abstract interface allows future migration to ChromaDB, FAISS, or Pinecone
- No additional dependencies for vector operations initially
- Retrieval uses keyword matching and BM25 scoring

**Alternatives Considered:**
- Immediate vector DB: Adds complexity and dependencies for uncertain future need
- In-memory only: Loses data on restart

**Storage Interface:**
```python
class DocumentStore(ABC):
    def add_documents(self, documents: List[Document]) -> None
    def search(self, query: str, top_k: int) -> List[Document]
    def delete_all(self) -> None
```

Implementations: `PageIndexStore` (initial), `VectorStore` (future)

### 5. Internet Search: DuckDuckGo Search API
**Decision:** Use DuckDuckGo search via `duckduckgo-search` Python library (no API key required).

**Rationale:**
- No API key or rate limits for personal use
- Privacy-focused (aligns with personal use case)
- Simple integration with LangChain tools

**Alternatives Considered:**
- Google Custom Search: Requires API key and has rate limits
- Bing Search: Requires API key
- SerpAPI: Paid service

### 6. Configuration Management: YAML with Pydantic Validation
**Decision:** Single `config.yaml` file with Pydantic models for validation and type safety.

**Rationale:**
- YAML is human-readable and easy to edit
- Pydantic ensures type safety and validation
- Single source of truth for all configuration

**Configuration Structure:**
```yaml
llm:
  model_name: "mistralai/Mistral-7B-Instruct-v0.2"
  quantization: "4bit"
  max_tokens: 512
  temperature: 0.7

rag:
  storage_type: "page_index"  # Future: "vector_db"
  chunk_size: 1000
  chunk_overlap: 200
  top_k: 3

search:
  provider: "duckduckgo"
  max_results: 5

server:
  host: "localhost"
  port: 8000
```

### 7. Document Processing: LangChain Text Splitters
**Decision:** Use LangChain's `RecursiveCharacterTextSplitter` for chunking documents.

**Rationale:**
- Handles various document formats (PDF, TXT, MD)
- Configurable chunk size and overlap
- Preserves semantic boundaries

### 8. MCP Client Integration: Dynamic Tool Loading
**Decision:** Implement MCP client to connect to external MCP servers and dynamically load their tools as LangChain tools.

**Rationale:**
- Enables access to external tools (file systems, databases, APIs) like Claude Desktop
- MCP servers configured in YAML with connection details
- Tools from MCP servers automatically available to LangChain agent
- Supports stdio and SSE transport protocols

**Alternatives Considered:**
- Hardcoded tool integrations: Not extensible, requires code changes for new tools
- Custom protocol: MCP is standardized and has growing ecosystem

**MCP Client Architecture:**
```python
class MCPClientManager:
    def connect_server(self, server_config: MCPServerConfig) -> MCPClient
    def list_tools(self, server_name: str) -> List[Tool]
    def call_tool(self, server_name: str, tool_name: str, args: dict) -> Any
```

Integration: Wrap MCP tools as LangChain tools for agent use

### 9. MCP Server Mode: Hybrid and Headless Operation
**Decision:** Support three operational modes - hybrid (chatbot + MCP server), chatbot-only, and MCP server-only (headless).

**Rationale:**
- **Hybrid mode** (default): Run chatbot with web UI AND expose MCP server simultaneously for maximum flexibility
- **Chatbot-only**: When MCP server exposure not needed
- **Headless MCP server**: Reduces resource usage when LLM not needed (no model loading)
- Allows other LLM applications (Claude Desktop, custom clients) to use this app's RAG and search
- Reuses existing RAG and search implementations across all modes

**Alternatives Considered:**
- Separate MCP server application: Code duplication and maintenance overhead
- Only hybrid mode: Wastes resources when MCP server not needed
- Only separate modes: Less convenient for typical use case

**MCP Server Tools Exposed:**
- `search_documents`: Query RAG knowledge base
- `search_web`: Perform internet search via DuckDuckGo
- `add_documents`: Ingest new documents to RAG index
- `list_documents`: List indexed documents

**Configuration:**
```yaml
mode: "hybrid"  # or "chatbot" or "mcp_server"
server:
  host: "localhost"
  port: 8000
mcp_server:
  enabled: true  # auto-enabled in hybrid/mcp_server modes
  transport: "sse"  # "stdio" or "sse"
  name: "rag-search-server"
  port: 8001  # for SSE transport
```

**Mode Behavior:**
- `hybrid`: FastAPI web server (port 8000) + MCP server (stdio or SSE on port 8001)
- `chatbot`: FastAPI web server only (port 8000)
- `mcp_server`: MCP server only (stdio or SSE), no LLM loaded

## Risks / Trade-offs

**Risk: Model inference latency on M3**
→ Mitigation: Use quantized models, implement response streaming, cache frequent queries

**Risk: Page-based indexing may not scale beyond 1000s of documents**
→ Mitigation: Abstract storage interface allows migration to vector DB when needed

**Risk: Internet search results may be rate-limited or blocked**
→ Mitigation: Implement fallback to cached results, configurable search provider

**Risk: Memory pressure with large context windows**
→ Mitigation: Limit conversation history to last 10 messages, implement context pruning

**Trade-off: Page indexing vs Vector DB**
- Page indexing: Simpler, faster setup, but less semantic retrieval quality
- Accepted for initial version, architecture supports future upgrade

**Trade-off: Local-only deployment**
- Limits accessibility to single machine
- Accepted as personal use case, could add ngrok tunnel if needed

## Migration Plan

**Initial Deployment:**
1. Install Python dependencies via `requirements.txt`
2. Create `config.yaml` with default settings
3. Run document ingestion script to populate RAG index
4. Start FastAPI server on localhost:8000
5. Access web UI via browser

**Rollback Strategy:**
- N/A for initial deployment (greenfield)

**Future Vector DB Migration:**
1. Implement `VectorStore` class conforming to `DocumentStore` interface
2. Update `config.yaml` to set `storage_type: "vector_db"`
3. Run migration script to re-index documents
4. No code changes required in retrieval logic

## Open Questions

1. **Document format support:** Should we support Office formats (DOCX, XLSX) or start with plain text/PDF/Markdown?
   - Recommendation: Start with TXT, PDF, MD; add Office support if needed

2. **Conversation persistence:** Should chat history be saved to disk or kept in-memory only?
   - Recommendation: Save to SQLite for persistence across restarts

3. **Model download location:** Where should HuggingFace models be cached?
   - Recommendation: Use default HuggingFace cache (`~/.cache/huggingface`)
