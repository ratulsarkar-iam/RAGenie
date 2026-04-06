## 1. Project Setup and Configuration

- [x] 1.1 Create project directory structure (src/, config/, data/, static/, templates/)
- [x] 1.2 Create requirements.txt with all dependencies (transformers, langchain, fastapi, mcp, etc.)
- [x] 1.3 Create default config.yaml with all configuration sections (including MCP)
- [x] 1.4 Implement Pydantic configuration models for validation
- [x] 1.5 Create configuration loader with environment variable override support
- [x] 1.6 Add inline documentation to config.yaml explaining each parameter
- [x] 1.7 Add mode selection configuration (hybrid, chatbot, or mcp_server with hybrid as default)

## 2. Core Infrastructure

- [x] 2.1 Implement abstract DocumentStore interface (ABC)
- [x] 2.2 Create Document and Chunk data models
- [x] 2.3 Set up logging configuration
- [x] 2.4 Create utility functions for file handling and text processing
- [x] 2.5 Implement error handling decorators and custom exceptions

## 3. LLM Integration

- [x] 3.1 Implement HuggingFace model loader with quantization support
- [x] 3.2 Add MPS device detection and allocation for Mac M3
- [x] 3.3 Create LangChain HuggingFacePipeline wrapper
- [x] 3.4 Implement text generation with configurable parameters
- [x] 3.5 Add streaming token generation support
- [x] 3.6 Implement memory optimization (gradient checkpointing, cache clearing)
- [x] 3.7 Add model loading error handling and fallback mechanisms
- [x] 3.8 Create prompt template system with LangChain

## 4. RAG System - Page Index Implementation

- [x] 4.1 Implement PageIndexStore class conforming to DocumentStore interface
- [x] 4.2 Create document chunking using RecursiveCharacterTextSplitter
- [x] 4.3 Implement BM25 keyword-based search algorithm
- [x] 4.4 Add document metadata storage and retrieval
- [x] 4.5 Implement JSON-based persistence (save/load index)
- [x] 4.6 Create LangChain BaseRetriever wrapper for PageIndexStore
- [x] 4.7 Implement context augmentation logic (prepend chunks to prompts)
- [x] 4.8 Add document deletion and index clearing functionality

## 5. Document Ingestion Pipeline

- [x] 5.1 Create document loader for TXT files
- [x] 5.2 Create document loader for PDF files (using PyPDF2 or pdfplumber)
- [x] 5.3 Create document loader for Markdown files
- [x] 5.4 Implement document preprocessing (text normalization, cleaning)
- [x] 5.5 Add metadata extraction from files
- [x] 5.6 Implement batch processing for multiple documents
- [x] 5.7 Create CLI script for document ingestion
- [x] 5.8 Add duplicate detection using content hashing
- [x] 5.9 Implement progress tracking and error reporting

## 6. Internet Search Integration

- [x] 6.1 Integrate duckduckgo-search library
- [x] 6.2 Create search service with configurable provider
- [x] 6.3 Implement search result extraction and formatting
- [x] 6.4 Add result limiting based on config.yaml
- [x] 6.5 Create LangChain tool wrapper for search functionality
- [x] 6.6 Implement search result caching with TTL
- [x] 6.7 Add search query optimization logic
- [x] 6.8 Implement error handling for search failures

## 7. MCP Client Integration

- [ ] 7.1 Install MCP Python SDK dependency
- [ ] 7.2 Implement MCPClientManager for managing multiple server connections
- [ ] 7.3 Add support for stdio transport protocol
- [ ] 7.4 Add support for SSE transport protocol
- [ ] 7.5 Implement dynamic tool discovery from MCP servers
- [ ] 7.6 Create LangChain tool wrappers for MCP tools
- [ ] 7.7 Implement tool execution with argument validation
- [ ] 7.8 Add resource access functionality for MCP servers
- [ ] 7.9 Implement connection error handling and retry logic
- [ ] 7.10 Add MCP server configuration parsing from YAML

## 8. MCP Server Implementation

- [ ] 8.1 Implement MCP server base with stdio transport
- [ ] 8.2 Add SSE transport support for MCP server
- [ ] 8.3 Create search_documents tool handler
- [ ] 8.4 Create search_web tool handler
- [ ] 8.5 Create add_documents tool handler
- [ ] 8.6 Create list_documents tool handler
- [ ] 8.7 Implement server metadata and capabilities
- [ ] 8.8 Add resource exposure for indexed documents
- [ ] 8.9 Implement tool argument validation and error handling
- [ ] 8.10 Implement mode selection logic (hybrid, chatbot-only, mcp_server-only)

## 9. Chat Orchestration

- [x] 9.1 Create conversation manager with history tracking
- [x] 9.2 Implement LangChain agent with RAG, search, and MCP tools
- [x] 9.3 Add conversation history pruning (limit to last 10 messages)
- [x] 9.4 Implement SQLite-based conversation persistence
- [x] 9.5 Create chat service coordinating LLM, RAG, search, and MCP tools
- [x] 9.6 Add context length management and truncation
- [x] 9.7 Implement streaming response handler

## 10. FastAPI Backend

- [x] 10.1 Create FastAPI application with CORS configuration
- [x] 10.2 Implement WebSocket endpoint for streaming chat
- [x] 10.3 Create REST endpoint for chat history retrieval
- [x] 10.4 Add endpoint for clearing conversation history
- [x] 10.5 Implement document upload endpoint (web UI)
- [x] 10.6 Create endpoint for listing indexed documents
- [x] 10.7 Add endpoint for deleting documents
- [x] 10.8 Implement health check and status endpoints
- [x] 10.9 Add async request handling for non-blocking inference
- [ ] 10.10 Add endpoint for listing connected MCP servers and tools

## 11. Frontend - React Chat Interface

- [x] 11.1 Set up React project with Vite and TypeScript
- [x] 11.2 Install and configure Tailwind CSS
- [x] 11.3 Create responsive layout component (desktop/mobile)
- [x] 11.4 Implement message display component with user/AI styling
- [x] 11.5 Add markdown rendering support for AI responses
- [x] 11.6 Create input component with Enter/Shift+Enter handling
- [x] 11.7 Implement conversation history display
- [x] 11.8 Add loading states and animations
- [x] 11.9 Create sidebar for document list and statistics
- [x] 11.10 Implement WebSocket connection for streaming responses
- [x] 11.11 Add error handling and retry logic
- [x] 11.12 Create document upload interface
- [x] 11.13 Add conversation management (new/clear/switch)
- [x] 11.14 Implement responsive mobile design
- [x] 11.15 Add dark/light theme toggle breakpoints
- [x] 11.15 Add UI for viewing connected MCP servers and available tools

## 12. Integration and Testing

- [ ] 12.1 Test HuggingFace model loading on Mac M3
- [ ] 12.2 Test document ingestion with sample files
- [ ] 12.3 Verify RAG retrieval with test queries
- [ ] 12.4 Test internet search integration
- [ ] 12.5 Test MCP client connection to external servers
- [ ] 12.6 Verify MCP tool discovery and execution
- [ ] 12.7 Test MCP server mode (headless operation)
- [ ] 12.8 Verify MCP server tool exposure to external clients
- [ ] 12.9 Test agent with combined RAG, search, and MCP tools
- [ ] 12.10 Verify WebSocket streaming functionality
- [ ] 12.11 Test responsive UI on desktop and mobile browsers
- [ ] 12.12 Verify configuration file changes apply correctly
- [ ] 12.13 Test conversation persistence across restarts
- [ ] 12.14 Verify memory usage stays within 16GB constraints
- [ ] 12.15 Test error handling and fallback mechanisms

## 13. Documentation and Deployment

- [ ] 13.1 Create README with installation instructions
- [ ] 13.2 Document configuration options in detail (including MCP)
- [ ] 13.3 Add usage examples and screenshots
- [ ] 13.4 Create troubleshooting guide
- [ ] 13.5 Document model recommendations for Mac M3
- [ ] 13.6 Add instructions for document ingestion
- [ ] 13.7 Document MCP client setup and server configuration
- [ ] 13.8 Document MCP server mode usage and integration with Claude Desktop
- [ ] 13.9 Document hybrid mode (default) operation
- [ ] 13.10 Create startup script for hybrid mode (default)
- [ ] 13.11 Create startup script for chatbot-only mode
- [ ] 13.12 Create startup script for MCP server-only mode
- [ ] 13.13 Document future vector DB migration path
- [ ] 13.14 Add example MCP server configurations
