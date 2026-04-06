## ADDED Requirements

### Requirement: YAML configuration file
The system SHALL use a single YAML configuration file for all system parameters.

#### Scenario: Load configuration on startup
- **WHEN** application starts
- **THEN** system reads config.yaml and initializes all components with specified parameters

#### Scenario: Missing configuration file
- **WHEN** config.yaml does not exist
- **THEN** system creates default configuration file with sensible defaults

### Requirement: Configuration validation
The system SHALL validate configuration values using Pydantic models for type safety.

#### Scenario: Valid configuration
- **WHEN** config.yaml contains valid parameters
- **THEN** system loads configuration without errors

#### Scenario: Invalid configuration
- **WHEN** config.yaml contains invalid types or values
- **THEN** system displays detailed validation errors and refuses to start

#### Scenario: Missing required fields
- **WHEN** required configuration fields are absent
- **THEN** system uses default values and logs warnings

### Requirement: LLM configuration
The system SHALL support configuration of model name, quantization, generation parameters, and device settings.

#### Scenario: Configure model parameters
- **WHEN** user sets llm.model_name, llm.temperature, llm.max_tokens in config.yaml
- **THEN** system applies these parameters during model initialization and generation

#### Scenario: Quantization settings
- **WHEN** user sets llm.quantization to "4bit", "8bit", or "none"
- **THEN** system loads model with specified quantization level

### Requirement: RAG configuration
The system SHALL support configuration of storage type, chunking parameters, and retrieval settings.

#### Scenario: Configure storage backend
- **WHEN** user sets rag.storage_type to "page_index" or "vector_db"
- **THEN** system initializes appropriate DocumentStore implementation

#### Scenario: Configure chunking
- **WHEN** user sets rag.chunk_size and rag.chunk_overlap
- **THEN** system uses these values for document splitting

#### Scenario: Configure retrieval
- **WHEN** user sets rag.top_k
- **THEN** system retrieves specified number of document chunks

### Requirement: Search configuration
The system SHALL support configuration of search provider and result limits.

#### Scenario: Configure search provider
- **WHEN** user sets search.provider in config.yaml
- **THEN** system uses specified provider for internet searches

#### Scenario: Configure result limit
- **WHEN** user sets search.max_results
- **THEN** system limits search results to specified count

### Requirement: Server configuration
The system SHALL support configuration of host, port, and CORS settings.

#### Scenario: Configure server endpoint
- **WHEN** user sets server.host and server.port
- **THEN** system starts FastAPI server on specified host and port

#### Scenario: Default server settings
- **WHEN** server configuration is not specified
- **THEN** system uses localhost:8000 as default

### Requirement: Mode configuration
The system SHALL support configuration of operational mode (hybrid, chatbot, or mcp_server).

#### Scenario: Configure hybrid mode
- **WHEN** user sets mode to "hybrid" in config.yaml
- **THEN** system starts both FastAPI web server and MCP server

#### Scenario: Configure chatbot-only mode
- **WHEN** user sets mode to "chatbot" in config.yaml
- **THEN** system starts FastAPI web server without MCP server

#### Scenario: Configure MCP server-only mode
- **WHEN** user sets mode to "mcp_server" in config.yaml
- **THEN** system starts MCP server without loading LLM or web server

#### Scenario: Default mode
- **WHEN** mode is not specified in config.yaml
- **THEN** system defaults to "hybrid" mode

### Requirement: MCP server configuration
The system SHALL support configuration of MCP server transport, name, and port settings.

#### Scenario: Configure MCP server transport
- **WHEN** user sets mcp_server.transport to "stdio" or "sse"
- **THEN** system uses specified transport protocol for MCP server

#### Scenario: Configure MCP server name
- **WHEN** user sets mcp_server.name in config.yaml
- **THEN** system uses specified name in MCP server metadata

#### Scenario: Configure SSE port
- **WHEN** user sets mcp_server.port and transport is "sse"
- **THEN** system starts MCP server HTTP endpoint on specified port

#### Scenario: Default MCP server settings
- **WHEN** MCP server settings are not specified
- **THEN** system uses defaults (transport: sse, port: 8001, name: rag-search-server)

### Requirement: Hot reload support
The system SHALL detect configuration changes and allow reload without full restart where possible.

#### Scenario: Reload generation parameters
- **WHEN** user modifies generation parameters in config.yaml
- **THEN** system applies new parameters to subsequent requests without restart

#### Scenario: Model change requires restart
- **WHEN** user changes llm.model_name
- **THEN** system logs message indicating restart is required for model change

#### Scenario: Mode change requires restart
- **WHEN** user changes mode in config.yaml
- **THEN** system logs message indicating restart is required for mode change

### Requirement: Configuration documentation
The system SHALL provide inline comments in default config.yaml explaining each parameter.

#### Scenario: Generate documented config
- **WHEN** system creates default config.yaml
- **THEN** file includes comments describing each parameter and valid values

#### Scenario: Example configurations
- **WHEN** user needs configuration examples
- **THEN** system provides config.example.yaml with multiple preset configurations

### Requirement: Environment variable override
The system SHALL support overriding configuration values via environment variables.

#### Scenario: Override via environment
- **WHEN** environment variable matches config path (e.g., LLM_MODEL_NAME)
- **THEN** system uses environment value instead of config.yaml value

#### Scenario: Precedence order
- **WHEN** same parameter exists in environment and config file
- **THEN** system prioritizes environment variable over config file
