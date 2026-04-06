## ADDED Requirements

### Requirement: MCP server mode operation
The system SHALL support three operational modes: hybrid, chatbot-only, and MCP server-only.

#### Scenario: Start in hybrid mode
- **WHEN** application is configured with mode "hybrid"
- **THEN** system starts FastAPI web server with LLM AND MCP server simultaneously

#### Scenario: Start in chatbot-only mode
- **WHEN** application is configured with mode "chatbot"
- **THEN** system starts FastAPI web server with LLM without MCP server

#### Scenario: Start in MCP server-only mode
- **WHEN** application is configured with mode "mcp_server"
- **THEN** system starts MCP server without initializing HuggingFace model or web server

### Requirement: Tool exposure
The system SHALL expose RAG and search capabilities as MCP tools to external clients.

#### Scenario: Expose search_documents tool
- **WHEN** MCP client requests tool list
- **THEN** system includes search_documents tool with schema for querying RAG knowledge base

#### Scenario: Expose search_web tool
- **WHEN** MCP client requests tool list
- **THEN** system includes search_web tool with schema for internet search

#### Scenario: Expose add_documents tool
- **WHEN** MCP client requests tool list
- **THEN** system includes add_documents tool with schema for document ingestion

#### Scenario: Expose list_documents tool
- **WHEN** MCP client requests tool list
- **THEN** system includes list_documents tool with schema for listing indexed documents

### Requirement: Tool execution handlers
The system SHALL implement handlers for each exposed MCP tool.

#### Scenario: Handle search_documents request
- **WHEN** MCP client calls search_documents tool
- **THEN** system queries RAG index and returns relevant document chunks

#### Scenario: Handle search_web request
- **WHEN** MCP client calls search_web tool
- **THEN** system performs DuckDuckGo search and returns formatted results

#### Scenario: Handle add_documents request
- **WHEN** MCP client calls add_documents tool
- **THEN** system ingests provided documents and returns success status

#### Scenario: Handle list_documents request
- **WHEN** MCP client calls list_documents tool
- **THEN** system returns list of indexed documents with metadata

### Requirement: Transport protocol support
The system SHALL support stdio and SSE transport protocols for MCP server.

#### Scenario: Serve via stdio transport
- **WHEN** MCP server is configured with stdio transport
- **THEN** system communicates with client via stdin/stdout

#### Scenario: Serve via SSE transport
- **WHEN** MCP server is configured with SSE transport
- **THEN** system starts HTTP server and handles SSE connections

### Requirement: Server metadata
The system SHALL provide server information and capabilities to MCP clients.

#### Scenario: Return server info
- **WHEN** MCP client requests server information
- **THEN** system returns server name, version, and protocol version

#### Scenario: Advertise capabilities
- **WHEN** MCP client queries capabilities
- **THEN** system advertises support for tools and resources

### Requirement: Resource exposure
The system SHALL optionally expose indexed documents as MCP resources.

#### Scenario: List document resources
- **WHEN** MCP client requests resource list
- **THEN** system returns URIs for all indexed documents

#### Scenario: Read document resource
- **WHEN** MCP client requests specific document resource
- **THEN** system returns full document content with metadata

### Requirement: Error handling
The system SHALL handle invalid tool calls and return appropriate error responses.

#### Scenario: Invalid tool name
- **WHEN** MCP client calls non-existent tool
- **THEN** system returns error with list of available tools

#### Scenario: Invalid tool arguments
- **WHEN** MCP client provides invalid arguments to tool
- **THEN** system validates against schema and returns detailed validation error

#### Scenario: Tool execution failure
- **WHEN** tool execution fails internally
- **THEN** system returns error with failure reason and logs details

### Requirement: Configuration
The system SHALL support configuring MCP server settings via YAML.

#### Scenario: Configure server name
- **WHEN** mcp_server.name is set in config.yaml
- **THEN** system uses configured name in server metadata

#### Scenario: Configure transport protocol
- **WHEN** mcp_server.transport is set in config.yaml
- **THEN** system uses specified transport (stdio or sse)

#### Scenario: Configure SSE endpoint
- **WHEN** mcp_server.transport is sse and port is configured
- **THEN** system starts HTTP server on specified port for SSE connections
