# RAGenie

An open-source AI assistant powered by **Retrieval-Augmented Generation (RAG)** with local LLMs, internet search, multi-model orchestration, and data analytics — all running on your own hardware.

![Python](https://img.shields.io/badge/Python-3.9+-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green?logo=fastapi)
![React](https://img.shields.io/badge/React-18-blue?logo=react)
![Ollama](https://img.shields.io/badge/Ollama-Local%20LLMs-black?logo=ollama)
![License](https://img.shields.io/badge/License-MIT-yellow)

> 💡 **New to RAGenie?** Read [**DAILY_VALUE.md**](DAILY_VALUE.md) — a plain-English guide to what RAGenie does for you every day and how much time it saves.

---

## Features

- **Local LLMs via Ollama** — Run models like Gemma 4, Qwen 2.5, DeepSeek-R1, Llama 3.2 entirely on your machine. No API keys, no cloud dependency.
- **RAG System** — Ingest documents (PDF, TXT, Markdown, DOCX, Excel, images, audio), chunk and index them with BM25, and retrieve relevant context for every query.
- **Multi-Model Architecture** — Assign different models to different roles: a reasoning model for chain-of-thought analysis, a main model for responses, and a fallback for reliability.
- **Internet Search** — DuckDuckGo integration for real-time web information, with result caching.
- **Data Analytics** — Upload CSV/Excel/JSON data, run statistical analysis, build regression/classification models, and generate interactive Plotly visualizations.
- **Chat File Upload** — Attach files directly in the chat (drag-and-drop or click), upload up to 30MB, and query their contents — just like ChatGPT or Gemini.
- **Search History** — Persistent search history with a dedicated side pane for filtering, selecting, and reusing past queries (localStorage-backed).
- **Modern Web UI** — React + TypeScript + Tailwind CSS frontend with dark/light theme toggle, glassmorphism design, WebSocket streaming, and document management.
- **MCP Server & Client** — Expose RAGenie tools via MCP (SSE/stdio) for Claude Desktop integration, *and* connect to any external MCP server to give the LLM access to 100s of third-party tools.
- **Authentication** — Optional JWT-based login with access tokens (30 min) and refresh tokens (7 days). Enable with a single config flag.
- **Persistent Memory** — SQLite-backed long-term memory that survives restarts. RAGenie remembers user preferences and injects relevant context into every prompt.
- **Learning Feedback Loop** — Users rate responses (👍/👎); scores adapt retrieval weights over time, making the assistant progressively smarter.
- **News Aggregator** — Fetches, scrapes, and LLM-summarises live news via DuckDuckGo. Supports 20+ language regions. Articles can optionally be ingested into the RAG index.
- **Proactive Capabilities** — Background scheduler sends daily briefings and context-aware nudges at a configurable hour with quiet-hour enforcement.
- **Task Execution** — MCP-based task clients for macOS Calendar and Reminders (stdio transport). Confirmation-gated for safety.
- **Security Hardening** — Rate limiting (slowapi), security headers, request-size caps, log redaction, and audit logging.
- **Fully Configurable** — Single YAML file controls every subsystem, with environment variable overrides for deployment flexibility.

---

## Presentation

A fully-designed PowerPoint overview deck (**22 slides**) is included in the repository:

```bash
python generate_presentation.py
# Output: RAGenie_Overview.pptx
```

The deck covers architecture, all major features, 6 detailed workflow blueprints (Chat Lifecycle, Document Ingestion, Analytics, MCP Tool-Call, Auth, Memory & Learning), API reference, technology stack, system requirements, and a comparison table.

Requires `python-pptx` and `lxml` (`pip install python-pptx lxml`).

---

## How It Works

RAGenie is a self-hosted AI assistant that combines four core capabilities — **chat**, **document knowledge**, **web search**, and **data analytics** — into a single application. Everything runs locally; no data leaves your machine.

### Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                        React Frontend                             │
│  Chat UI │ Analytics │ Documents │ MCP Servers │ News │ Login     │
└──────┬───────────┬──────────────┬───────────────┬───────────────┘
       │ WebSocket │ REST         │ REST          │ REST
       ▼           ▼              ▼               ▼
┌──────────────────────────────────────────────────────────────────┐
│                    FastAPI Backend (JWT Auth · Rate Limiting)      │
│                                                                   │
│  ┌─────────────┐  ┌───────────┐  ┌───────────┐  ┌────────────┐  │
│  │    Chat     │  │ Analytics │  │ Document  │  │  MCP Client│  │
│  │ Orchestrator│  │  Engine   │  │  Manager  │  │  Manager   │  │
│  └──────┬──────┘  └─────┬─────┘  └─────┬─────┘  └─────┬──────┘  │
│         │               │              │               │         │
│  ┌──────▼──────┐  ┌─────▼─────┐  ┌────▼──────┐  ┌─────▼──────┐  │
│  │Multi-Model  │  │Visualizer │  │ Ingestion │  │ External   │  │
│  │  Manager   │  │ (Plotly)  │  │ Pipeline  │  │MCP Servers │  │
│  └──────┬──────┘  └───────────┘  └─────┬─────┘  └────────────┘  │
│         │                              │                         │
│  ┌──────▼──────────────┐  ┌────────────▼───────┐                 │
│  │  RAG System (BM25)  │  │  Document Loaders  │                 │
│  │  + Context Builder  │  │  PDF/DOCX/Excel/   │                 │
│  └──────┬──────────────┘  │  Image/Audio/TXT   │                 │
│         │                 └────────────────────┘                 │
│  ┌──────▼──────────────┐  ┌────────────────────┐                 │
│  │   Search Service    │  │  Persistent Memory │                 │
│  │ (DuckDuckGo+Cache)  │  │  + Learning Loop   │                 │
│  └─────────────────────┘  └────────────────────┘                 │
│  ┌────────────────────┐   ┌────────────────────┐                 │
│  │  News Aggregator   │   │  Proactive Engine  │                 │
│  │  (DuckDuckGo News) │   │  (Scheduler/Nudge) │                 │
│  └────────────────────┘   └────────────────────┘                 │
└──────────────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────┐     ┌─────────────────────┐
│   Ollama (Local)     │     │  External MCP Tools  │
│  Reasoning LLM      │     │  Calendar · Reminders│
│  Main LLM           │     │  GitHub · Filesystem │
│  Fallback LLM       │     │  … any MCP server    │
└─────────────────────┘     └─────────────────────┘
```

### Request Lifecycle — Chat

1. **User sends a message** via the React frontend over a WebSocket connection.
2. The **WebSocket handler** (`websocket.py`) receives the message and optionally auto-detects whether reasoning is needed using keyword-pattern matching (`reasoning_detector.py`).
3. The **RAG system** (`page_index_store.py`) searches all ingested document chunks using BM25 keyword matching, with built-in medical term expansion for domain-specific queries. Top-k relevant chunks are retrieved.
4. The **Context Builder** (`context_builder.py`) assembles the retrieved chunks into a structured context block.
5. The **System Prompt** (`prompts.py`) is combined with the RAG context and user query to form the final LLM prompt.
6. The **Multi-Model Manager** (`multi_model_manager.py`) routes the prompt:
   - If **reasoning mode** is active: the reasoning model (e.g., DeepSeek-R1) generates a step-by-step analysis first, which is then fed to the main model (e.g., Gemma 4) to produce the final answer.
   - If **standard mode**: the main model generates the response directly. On failure, the fallback model (e.g., Qwen 2.5) takes over automatically.
7. Tokens are **streamed back** to the frontend in real-time via the WebSocket, providing a smooth typing effect.
8. The response is added to the **conversation history**, which is pruned to a configurable maximum length.

### Request Lifecycle — Analytics

1. User uploads a data file (CSV, Excel, JSON, TSV) through the Analytics tab.
2. The **Data Loader** (`data_loader.py`) parses the file into a pandas DataFrame.
3. The **Analytics Engine** (`analytics_engine.py`) runs statistical analysis:
   - Basic & advanced statistics (mean, median, std, skewness, kurtosis, correlations)
   - Outlier detection (IQR and Z-score methods)
   - Predictive modeling via scikit-learn (Linear Regression, Logistic Regression, Random Forest)
4. The **Visualizer** (`visualizer.py`) generates interactive Plotly charts (histogram, scatter, line, bar, box, heatmap, pie) — including auto-visualization that picks the best chart types based on column data types.
5. Results are returned as JSON with embedded Plotly chart specifications, rendered interactively in the frontend.

### Document Ingestion Pipeline

1. Files are uploaded via the UI or CLI and saved to `data/documents/`.
2. **Document Loaders** (`loaders.py`) extract text:
   - **PDF**: `pdfplumber` (with `PyPDF2` fallback)
   - **DOCX/DOC**: `python-docx` (paragraphs + tables)
   - **Excel/CSV**: `pandas` (all sheets, column metadata)
   - **Images**: `Pillow` for metadata + optional `pytesseract` OCR
   - **Audio**: `mutagen` for metadata + optional `SpeechRecognition` transcription
   - **TXT/Markdown**: direct read with normalization
3. The **Chunker** (`chunker.py`) splits text into overlapping chunks (default: 1000 chars, 200 overlap) to preserve context at boundaries.
4. Each chunk gets a unique ID derived from its content hash (SHA-256) for deduplication.
5. Chunks are added to the **BM25 index** (`page_index_store.py`) and persisted to `data/index/page_index.json`.

### Key Design Decisions

- **BM25 over vector embeddings** — Fast, dependency-light keyword search that works well for structured documents without requiring GPU-heavy embedding models. No external vector database needed.
- **Ollama over cloud APIs** — Complete data privacy. Models run locally via Ollama's optimized inference engine with automatic hardware acceleration (Metal on Mac, CUDA on NVIDIA).
- **Multi-model with automatic fallback** — Reliability through redundancy. If the main model fails or times out, the fallback model ensures the user always gets a response.
- **Auto-reasoning detection** — The system automatically routes complex queries (step-by-step, analytical, mathematical) to the reasoning model without user intervention, using keyword pattern matching.
- **WebSocket streaming** — Token-by-token streaming via LangChain's `astream()` provides immediate feedback instead of waiting for the full response.
- **Single YAML config** — All settings (LLM, RAG, search, server, MCP, logging) in one file with environment variable overrides for deployment flexibility.

---

## Table of Contents

- [Daily Value Guide](DAILY_VALUE.md)
- [How It Works](#how-it-works)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Configuration](#configuration)
- [Multi-Model Setup](#multi-model-setup)
- [Document Management](#document-management)
- [Analytics](#analytics)
- [Authentication](#authentication)
- [MCP Server](#mcp-server)
- [MCP Client](#mcp-client)
- [Persistent Memory](#persistent-memory)
- [Learning & Feedback](#learning--feedback)
- [Proactive Capabilities](#proactive-capabilities)
- [News Aggregator](#news-aggregator)
- [Security](#security)
- [Task Execution](#task-execution)
- [API Reference](#api-reference)
- [Frontend](#frontend)
- [Presentation](#presentation)
- [Project Structure](#project-structure)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)
- [Acknowledgments](#acknowledgments)

---

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/ratulsarkar-iam/RAGenie.git
cd RAGenie

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Install Ollama and pull a model
# Install Ollama from https://ollama.com
ollama pull llama3.2

# 5. Create required directories
mkdir -p data/documents data/index logs

# 6. Start the backend
python run_server.py

# 7. Start the frontend (in a new terminal)
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` in your browser. Backend API is at `http://localhost:8000`.

> **One-command start:** Use `./start.sh` to launch both backend and frontend together.

---

## Installation

### Prerequisites

| Requirement | Minimum | Recommended |
|---|---|---|
| **Python** | 3.9+ | 3.11+ |
| **Node.js** | 16+ | 18+ |
| **RAM** | 8 GB | 16 GB |
| **Disk** | 5 GB | 20 GB (with models) |
| **Ollama** | Latest | Latest |

### Backend Setup

```bash
cd RAGenie
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
mkdir -p data/documents data/index logs
```

### Frontend Setup

```bash
cd frontend
npm install
```

### Install Ollama Models

```bash
# Install at least one model (pick what fits your hardware)
ollama pull llama3.2          # 2 GB — lightweight, good fallback
ollama pull qwen2.5:7b        # 4.7 GB — strong general-purpose
ollama pull deepseek-r1:1.5b  # 1.1 GB — specialized reasoning
ollama pull gemma4:e2b-it-q4_K_M  # 7.2 GB — large, high quality
```

---

## Configuration

All settings live in `config/config.yaml`.

### Operational Modes

```yaml
# "chatbot"    — Web UI only
# "hybrid"     — Web UI + MCP server (default)
# "mcp_server" — MCP server only (headless)
mode: "hybrid"
```

### LLM Settings

```yaml
llm:
  provider: "ollama"           # "ollama" or "huggingface"
  model_name: "llama3.2"       # Default single-model
  base_url: "http://localhost:11434"
  max_tokens: 512
  temperature: 0.7
  top_p: 0.9
  top_k: 50
  device: "mps"                # "mps" (Mac), "cuda" (NVIDIA), "cpu"
```

### RAG Settings

```yaml
rag:
  storage_type: "page_index"
  chunk_size: 1000             # Characters per chunk
  chunk_overlap: 200           # Overlap between chunks
  top_k: 3                     # Chunks to retrieve per query
  index_path: "data/index/page_index.json"
```

### Search Settings

```yaml
search:
  provider: "duckduckgo"
  max_results: 5
  cache_ttl_seconds: 3600      # Cache results for 1 hour
```

### Environment Variable Overrides

```bash
export LLM_MODEL_NAME="qwen2.5:7b"
export LLM_TEMPERATURE="0.8"
export RAG_CHUNK_SIZE="1500"
export SERVER_PORT="8080"
```

---

## Multi-Model Setup

RAGenie can use multiple LLMs simultaneously, each assigned a role:

| Role | Purpose | Example Model |
|---|---|---|
| **Reasoning** | Step-by-step analysis before answering | `deepseek-r1:1.5b` |
| **Main** | Primary response generation | `gemma4:e2b-it-q4_K_M` |
| **Fallback** | Backup if main model fails | `qwen2.5:7b` |

### Configuration

```yaml
llm:
  multi_model:
    reasoning:
      provider: "ollama"
      model_name: "deepseek-r1:1.5b"
      temperature: 0.3          # Lower for focused reasoning
      role: "reasoning"
    main:
      provider: "ollama"
      model_name: "gemma4:e2b-it-q4_K_M"
      temperature: 0.7
      role: "main"
    fallback:
      provider: "ollama"
      model_name: "qwen2.5:7b"
      temperature: 0.7
      role: "fallback"
```

### How It Works

**Standard mode** (reasoning off):
```
User Query → Main Model → Response
               ↓ (on failure)
          Fallback Model → Response
```

**Reasoning mode** (reasoning on):
```
User Query → Reasoning Model → Analysis
                                  ↓
                          Main Model (with reasoning context) → Response
```

### Disabling Multi-Model

Comment out or remove the `multi_model` section to use single-model mode with `model_name`.

---

## Document Management

### Supported Formats

| Category | Extensions |
|---|---|
| **Documents** | `.pdf`, `.txt`, `.md`, `.markdown`, `.docx`, `.doc` |
| **Spreadsheets** | `.xlsx`, `.xls`, `.csv` |
| **Images** | `.jpg`, `.jpeg`, `.png`, `.gif`, `.bmp`, `.webp`, `.tiff`, `.svg` |
| **Audio** | `.mp3`, `.wav`, `.ogg`, `.flac`, `.m4a`, `.aac`, `.wma` |

> **File size limit**: 30MB per file.
>
> **Image OCR**: Install `pytesseract` for automatic text extraction from images.
>
> **Audio transcription**: Install `SpeechRecognition` for WAV transcription via Google Speech API.

### Ingest Documents

**Via CLI:**
```bash
# Single file
python scripts/ingest_documents.py path/to/document.pdf

# Entire directory
python scripts/ingest_documents.py -r data/documents/
```

**Via Web UI (sidebar):**
1. Open the sidebar
2. Click "Upload Document"
3. Select a file — it's automatically chunked and indexed

**Via Chat (inline upload):**
1. Click the 📎 attach button in the chat input, or drag-and-drop files onto the input area
2. Add an optional message (e.g., "Summarize this document")
3. Press Send — files are uploaded, ingested into the RAG index, and the LLM responds with context from the file

This works like ChatGPT or Gemini: upload a file and immediately ask questions about it.

### How It Works

1. Document is uploaded and saved to `data/documents/`
2. Text is extracted and split into chunks (configurable size/overlap)
3. Chunks are indexed using BM25 for keyword search
4. Index is persisted to `data/index/page_index.json`

### Delete Documents

- **Web UI**: Hover over a document in the sidebar → click the trash icon
- **API**: `DELETE /api/documents/{doc_id}`

Both the index entry and the physical file are removed.

---

## Analytics

RAGenie includes a built-in analytics module for data exploration.

### Supported Data Formats

CSV, Excel (.xlsx/.xls), JSON, TSV, TXT, PDF (table extraction)

### Capabilities

| Feature | Description |
|---|---|
| **Basic Statistics** | Mean, median, std, min, max, quartiles, correlation matrix |
| **Advanced Statistics** | Skewness, kurtosis, IQR, mode |
| **Outlier Detection** | IQR method, Z-score method |
| **Regression** | Linear regression, Random Forest regression |
| **Classification** | Logistic regression, Random Forest classifier |
| **Time Series** | Trend analysis, future value prediction |
| **Visualization** | Histogram, scatter, line, bar, box, heatmap, pie chart (Plotly) |
| **Auto-Visualization** | Automatically generates relevant charts based on data types |

### Usage

1. Navigate to the **Analytics** tab in the web UI
2. Upload a data file (CSV, Excel, JSON, etc.)
3. Click **Run Complete Analysis** for insights
4. View auto-generated interactive charts
5. Use the **Predict** tab for trend forecasting

---

## Authentication

RAGenie ships with optional JWT-based authentication. It is **disabled by default** — flip one config flag to protect all endpoints.

### Enable Authentication

```yaml
auth:
  enabled: true
  db_path: "data/auth/users.db"
  access_token_expire_minutes: 30
  refresh_token_expire_days: 7
```

> **Important:** Set the `RAGENIE_SECRET_KEY` environment variable before enabling auth in production.

```bash
export RAGENIE_SECRET_KEY="your-long-random-secret"
```

### Auth Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/auth/register` | Create a new user account |
| `POST` | `/auth/login` | Obtain access + refresh tokens |
| `POST` | `/auth/refresh` | Exchange refresh token for new access token |
| `POST` | `/auth/logout` | Invalidate the current session |
| `GET` | `/auth/me` | Get the current user's profile |

### Token Flow

```
POST /auth/login  →  { access_token (30 min), refresh_token (7 days) }
       │
       ├─ Include in all requests: Authorization: Bearer <access_token>
       │
       └─ When expired: POST /auth/refresh  →  new access_token
```

---

## MCP Server

RAGenie can act as an **MCP server**, exposing its tools to any MCP-compatible client (e.g., Claude Desktop).

### Configuration

```yaml
mcp_server:
  enabled: true
  transport: "sse"    # "sse" for HTTP clients, "stdio" for Claude Desktop
  name: "rag-search-server"
  port: 8001
```

### Operational Modes

```yaml
mode: "hybrid"     # chatbot UI + MCP server (default)
# mode: "chatbot"  # UI only
# mode: "mcp_server"  # headless MCP server only
```

### Exposed Tools

**Core tools (5)**

| Tool | Description |
|---|---|
| `search_documents` | Search ingested documents using BM25 |
| `search_web` | Perform a DuckDuckGo web search |
| `list_documents` | List all indexed documents |
| `ask_ragenie` | Send a message and receive an AI response |
| `execute_task` | Delegate a task via MCP task clients |

**News tools (7)**

| Tool | Description |
|---|---|
| `list_news_keywords` | List all tracked news topics |
| `create_news_keyword` | Start tracking a new news topic |
| `update_news_keyword` | Change fetch interval, article cap, or enable/pause |
| `delete_news_keyword` | Stop tracking a topic |
| `fetch_news_now` | Trigger an immediate fetch by **keyword term** (e.g. `"IPL"`) |
| `get_news_articles` | Retrieve articles by **keyword term** — fuzzy match + LLM fallback |
| `suggest_news_keyword` | LLM-assisted keyword suggestion from a natural-language description |

### Claude Desktop Integration

Set `transport: "stdio"` and add to your Claude Desktop config:

```json
{
  "mcpServers": {
    "ragenie": {
      "command": "python",
      "args": ["/path/to/RAGenie/mcp_stdio.py"]
    }
  }
}
```

---

## MCP Client

RAGenie can also act as an **MCP client**, connecting to any external MCP server and injecting its tools directly into the LLM agent. Manage servers through the **MCP Servers** tab in the Web UI.

### Supported Transports

| Transport | Description |
|---|---|
| `stdio` | Launches a subprocess; communicates via stdin/stdout |
| `sse` | HTTP GET with Server-Sent Events (legacy) |
| `http` | Streamable HTTP POST (MCP protocol 2025-06-18) |

### How It Works

1. Register a server in the UI (name · transport · URL or command).
2. RAGenie stores the config in `data/mcp_client/servers.db` and opens a persistent connection.
3. On connect, it calls `list_tools()` to fetch all tool schemas.
4. Tools are registered in the LLM agent as `server_name/tool_name`.
5. When the LLM decides to call a tool, RAGenie proxies the call to the appropriate MCP server and returns the result.
6. Tools rebuild automatically on connect/disconnect — no restart needed.

### REST Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/mcp-servers` | List registered MCP servers |
| `POST` | `/mcp-servers` | Register a new MCP server |
| `GET` | `/mcp-servers/{id}` | Get server details |
| `PUT` | `/mcp-servers/{id}` | Update server config |
| `DELETE` | `/mcp-servers/{id}` | Remove a server |
| `POST` | `/mcp-servers/{id}/connect` | Connect to a server |
| `POST` | `/mcp-servers/{id}/disconnect` | Disconnect from a server |
| `GET` | `/mcp-servers/{id}/tools` | List tools from a connected server |
| `POST` | `/mcp-servers/{id}/call` | Manually invoke a tool |
| `GET` | `/mcp-servers/status` | Connection status of all servers |
| `GET` | `/mcp-servers/tools/all` | All tools across all connected servers |
| `POST` | `/mcp-servers/chat` | Agent chat using all connected MCP tools |

### Example: Add a Filesystem MCP Server

```json
{
  "name": "filesystem",
  "transport": "stdio",
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/dir"]
}
```

---

## Persistent Memory

RAGenie maintains a **long-term memory** across conversations, stored in SQLite.

### Configuration

```yaml
memory:
  enabled: true
  store_path: "data/memory/memories.db"
  max_context_items: 8    # max memories injected per prompt
  context_window: 2000    # characters per memory item
```

### How It Works

1. At the end of each conversation turn, important context phrases are extracted and stored.
2. On the next message, the top-8 most relevant memory items are retrieved and injected into the prompt.
3. Memories survive server restarts — they persist in SQLite.
4. The proactive engine uses stored memories to personalise daily briefings and nudges.

---

## Learning & Feedback

The feedback loop lets RAGenie improve its retrieval over time based on user ratings.

### Configuration

```yaml
learning:
  enabled: true
  adaptation_rate: 0.1
  positive_increment: 0.1   # score += 0.10 on 👍
  negative_decrement: 0.08  # score -= 0.08 on 👎
```

### Usage

After any AI response, click the 👍 or 👎 button. The backend updates that response's score in the database, which influences future BM25 retrieval ranking.

**API:**
```bash
POST /feedback/{message_id}
Content-Type: application/json
{ "positive": true }
```

---

## Proactive Capabilities

RAGenie can proactively send daily briefings and reminders without user prompting.

### Configuration

```yaml
proactive:
  enabled: true
  briefing_hour: 9             # send briefing at 09:00
  cycle_interval_minutes: 30   # check interval
  quiet_hours_start: 22        # no nudges after 10 PM
  quiet_hours_end: 8           # resume nudges after 8 AM
```

### What It Does

- **Daily Briefing** — At `briefing_hour`, generates a morning summary from recent news + stored memories.
- **Nudges** — Sends context-aware reminders during working hours based on previously stored user context.
- **Quiet Hours** — No proactive messages sent between `quiet_hours_start` and `quiet_hours_end`.

---

## News Aggregator

Built-in news fetcher that requires **no API key** — powered by DuckDuckGo News.

### Configuration

```yaml
news:
  enabled: true
  db_path: "data/news/news.db"
  region: "wt-wt"                       # worldwide (default)
  default_fetch_interval_minutes: 60
  default_max_articles_per_fetch: 10
  summarise_on_fetch: true               # LLM auto-summarises each article
  ingest_into_rag: false                 # set true to make articles searchable in chat
  max_content_chars: 8000
  summary_max_sentences: 5
  retention_days: 3                      # auto-delete older articles
  cleanup_interval_hours: 6
```

### Supported Regions

| Code | Region | Code | Region |
|---|---|---|---|
| `wt-wt` | Worldwide (default) | `us-en` | USA English |
| `in-en` | India English | `in-hi` | India Hindi |
| `in-bn` | India Bengali | `gb-en` | UK English |
| `de-de` | Germany | `fr-fr` | France |
| `jp-jp` | Japan | `xa-ar` | Arabic |

Keywords in any script (Devanagari, Tamil, etc.) work automatically with `wt-wt`.

### News REST Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/keywords` | List all tracked keywords |
| `POST` | `/api/keywords` | Create / start tracking a keyword |
| `GET` | `/api/keywords/{id}` | Get keyword details |
| `PATCH` | `/api/keywords/{id}` | Update keyword (interval, cap, enabled) |
| `DELETE` | `/api/keywords/{id}` | Delete keyword and stop tracking |
| `POST` | `/api/keywords/{id}/fetch-now` | Trigger an immediate news fetch |
| `GET` | `/api/news` | List fetched articles (paginated, filterable by `keyword_id`) |
| `POST` | `/api/keywords/suggest` | LLM-suggested keyword from natural-language description |

> **Keyword resolution:** MCP tools (`fetch_news_now`, `get_news_articles`) accept a plain-text topic name (e.g. `"IPL"`) and resolve it to the stored UUID automatically using exact match → substring match → LLM fallback.

---

## Security

RAGenie includes production-grade security hardening, all configurable via `config.yaml`.

```yaml
security:
  security_headers: true         # CSP, HSTS, X-Frame-Options, Referrer-Policy
  log_redaction: true            # scrub sensitive data from logs
  max_request_size_mb: 30        # reject bodies larger than 30 MB
  ws_max_message_length: 10000   # reject WebSocket messages over 10 000 chars
  audit_log_path: "logs/audit.log"
  rate_limiting:
    enabled: true
    default_rpm: 60              # requests per minute per IP
    upload_rph: 10               # uploads per hour per IP
    ws_rpm: 30                   # WebSocket messages per minute per client
```

### Security Headers Applied

| Header | Value |
|---|---|
| `X-Content-Type-Options` | `nosniff` |
| `X-Frame-Options` | `DENY` |
| `Content-Security-Policy` | Strict default-src |
| `Strict-Transport-Security` | `max-age=31536000` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |

### Audit Log

All write operations and auth events are written to `logs/audit.log` with sensitive fields redacted.

---

## Task Execution

RAGenie can execute real-world tasks via MCP-based task clients. Tasks requiring side-effects always prompt for confirmation first.

### Configuration

```yaml
tasks:
  enabled: true
  require_confirmation: true     # always ask before executing
  task_clients:
    - name: "calendar"
      enabled: false
      command: "python"
      args: ["mcp_clients/mcp_calendar_macos.py"]
    - name: "reminders"
      enabled: false
      command: "python"
      args: ["mcp_clients/mcp_reminders_macos.py"]
```

Set `enabled: true` on a client and `tasks.enabled: true` to activate. Currently ships with macOS Calendar and Reminders clients. Any MCP-compatible tool can be wired in as a task client.

---

## API Reference

### REST Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `POST` | `/chat` | Send a chat message |
| `GET` | `/history/{id}` | Get conversation history |
| `DELETE` | `/history/{id}` | Clear conversation |
| `GET` | `/documents` | List indexed documents |
| `POST` | `/upload` | Upload and ingest a document |
| `POST` | `/chat-upload` | Upload a file in chat context (ingest + return preview) |
| `DELETE` | `/documents/{id}` | Delete a document |

### Analytics Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/analytics/upload` | Upload a data file |
| `GET` | `/analytics/datasets` | List datasets |
| `GET` | `/analytics/datasets/{id}` | Get dataset details |
| `DELETE` | `/analytics/datasets/{id}` | Delete a dataset |
| `POST` | `/analytics/analyze/basic` | Basic statistics |
| `POST` | `/analytics/analyze/complete` | Full analysis |
| `POST` | `/analytics/predict/regression` | Regression analysis |
| `POST` | `/analytics/predict/future` | Future value prediction |
| `POST` | `/analytics/visualize` | Create visualization |
| `POST` | `/analytics/visualize/auto` | Auto-generate charts |

### WebSocket

| Endpoint | Description |
|---|---|
| `/ws/{client_id}` | Streaming chat (token-by-token) |

**Message format:**
```json
{
  "message": "Your question",
  "conversation_id": "session-1",
  "use_reasoning": false
}
```

### cURL Examples

```bash
# Health check
curl http://localhost:8000/health

# Chat
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello!", "conversation_id": "test"}'

# List documents
curl http://localhost:8000/documents

# Upload a document
curl -X POST http://localhost:8000/upload \
  -F "file=@document.pdf"

# Upload a file for chat querying
curl -X POST http://localhost:8000/chat-upload \
  -F "file=@report.docx"

# Upload analytics data
curl -X POST http://localhost:8000/analytics/upload \
  -F "file=@data.csv"
```

### Python Example

```python
from src.config.loader import load_config
from src.llm.langchain_wrapper import LangChainLLM
from src.rag.page_index_store import PageIndexStore
from src.search.search_service import SearchService
from src.chat.orchestrator import ChatOrchestrator

config = load_config()

rag_store = PageIndexStore(config.rag.index_path)
rag_store.load()

llm_wrapper = LangChainLLM(config.llm)
llm_wrapper.initialize()

search_service = SearchService(config.search)

orchestrator = ChatOrchestrator(
    llm_wrapper=llm_wrapper,
    rag_store=rag_store,
    search_service=search_service
)

orchestrator.start_conversation("my-session")
response = orchestrator.chat_simple("What is in my documents?")
print(response)
```

---

## Presentation

A fully-designed PowerPoint overview deck (**22 slides**) is generated from source:

```bash
python generate_presentation.py
# Output: RAGenie_Overview.pptx
```

Slide index:

| # | Slide |
|---|---|
| 1 | Cover |
| 2 | What is RAGenie? |
| 3 | System Architecture |
| 4 | RAG Document Pipeline |
| 5 | Multi-Model LLM Architecture |
| 6 | Core Capabilities |
| 7 | Data Analytics Module |
| 8 | MCP Integration |
| 9 | Security & Authentication |
| 10 | Persistent Memory & Learning |
| 11 | News Aggregator |
| 12 | Technology Stack |
| 13 | API Reference |
| 14 | Getting Started |
| 15 | System Requirements |
| 16 | Why RAGenie? (comparison table) |
| 17–22 | Workflow Blueprints (Chat · Documents · Analytics · MCP · Auth · Memory) |
| 23 | Closing |

Requires: `pip install python-pptx lxml`

---

## Frontend

The frontend is built with **React 18 + TypeScript + Vite + Tailwind CSS**.

### Features

- Real-time chat with WebSocket streaming
- **In-chat file upload** — attach files via 📎 button or drag-and-drop, with file preview chips
- **Search history pane** — side panel with filtering, query reuse, and clear controls (localStorage-persisted)
- **MCP Servers manager** — register, connect/disconnect, and inspect tools for external MCP servers
- **News Feed page** — browse fetched and summarised articles per feed
- **Login / Register** — JWT auth UI (shown when `auth.enabled: true`)
- Markdown rendering for AI responses
- Document management (upload, list, delete) in the sidebar
- Dark/light theme toggle (saved to localStorage)
- macOS-inspired glassmorphism design with modern ChatGPT-style input box
- Interactive Plotly charts for analytics
- Responsive layout

### Development

```bash
cd frontend
npm run dev      # Start dev server (http://localhost:5173)
npm run build    # Production build → dist/
npm run lint     # Run ESLint
```

### Key Dependencies

- `react`, `react-dom` — UI framework
- `react-markdown` — Markdown rendering
- `plotly.js`, `react-plotly.js` — Interactive charts
- `lucide-react` — Icons (including Paperclip, FileText, Image, Music, FileSpreadsheet)
- `axios` — HTTP client
- `tailwindcss` — Styling

---

## Project Structure

```
RAGenie/
├── config/
│   └── config.yaml                  # All application settings (single source of truth)
├── data/
│   ├── documents/                   # Uploaded/ingested documents
│   ├── index/                       # BM25 RAG index (page_index.json)
│   ├── auth/
│   │   └── users.db                 # User accounts (SQLite)
│   ├── mcp_client/
│   │   └── servers.db               # MCP client server configs (SQLite)
│   ├── memory/
│   │   └── memories.db              # Persistent memory store (SQLite)
│   ├── news/
│   │   └── news.db                  # News articles & feeds (SQLite)
│   └── conversations.db             # Conversation history (SQLite)
├── src/
│   ├── api/
│   │   ├── app.py                   # FastAPI application, startup, CORS, routes
│   │   ├── websocket.py             # WebSocket streaming handler
│   │   ├── analytics_routes.py      # Analytics API endpoints
│   │   └── mcp_client_routes.py     # MCP client REST endpoints (11 routes)
│   ├── analytics/
│   │   ├── data_loader.py           # Multi-format data parser (CSV/Excel/JSON/PDF)
│   │   ├── analytics_engine.py      # Statistical analysis & ML models
│   │   └── visualizer.py            # Plotly chart generation
│   ├── auth/
│   │   ├── dependencies.py          # FastAPI auth dependencies / JWT guards
│   │   ├── jwt_manager.py           # Token creation & validation
│   │   └── routes.py                # /auth/* endpoints
│   ├── chat/
│   │   └── orchestrator.py          # Chat orchestration, agent logic, MCP tool calls
│   ├── config/
│   │   ├── models.py                # Pydantic config models (all sections)
│   │   └── loader.py                # YAML + env-var config loader
│   ├── core/
│   │   ├── models.py                # Core data models (Document, Chunk, etc.)
│   │   ├── document_store.py        # Storage interface
│   │   ├── exceptions.py            # Custom exception hierarchy
│   │   └── logging_config.py        # Structured logging setup
│   ├── ingestion/
│   │   ├── loaders.py               # Document loaders (PDF/DOCX/Excel/Image/Audio/TXT)
│   │   └── pipeline.py              # Ingestion pipeline (upload → chunk → index)
│   ├── learning/
│   │   └── feedback.py              # Feedback loop & score adaptation
│   ├── llm/
│   │   ├── langchain_wrapper.py     # LangChain LLM integration
│   │   ├── multi_model_manager.py   # Reasoning / Main / Fallback model routing
│   │   ├── ollama_wrapper.py        # Ollama provider
│   │   ├── model_loader.py          # HuggingFace model loader
│   │   └── prompts.py               # System prompt & RAG prompt templates
│   ├── mcp/
│   │   └── server.py                # MCP server (SSE/stdio, exposes RAGenie tools)
│   ├── mcp_client/
│   │   ├── client.py                # Per-server MCP client (stdio/SSE/HTTP)
│   │   ├── manager.py               # MCPClientManager (registry + tool rebuild)
│   │   ├── models.py                # Pydantic models for server config
│   │   ├── server_store.py          # SQLite persistence for server configs
│   │   └── exceptions.py            # MCP client exceptions
│   ├── memory/
│   │   └── memory_store.py          # Persistent memory read/write (SQLite)
│   ├── news/
│   │   ├── fetcher.py               # DuckDuckGo News fetch + scrape
│   │   ├── models.py                # News article & feed models
│   │   ├── routes.py                # /news/* REST endpoints
│   │   └── scheduler.py             # Background fetch scheduler
│   ├── proactive/
│   │   └── engine.py                # Daily briefing + nudge scheduler
│   ├── rag/
│   │   ├── page_index_store.py      # BM25 index & search (+ medical term expansion)
│   │   ├── chunker.py               # Overlapping text chunker
│   │   ├── retriever.py             # LangChain retriever adapter
│   │   └── context_builder.py       # Context block assembly
│   ├── search/
│   │   ├── search_service.py        # DuckDuckGo search with 1-hour cache
│   │   └── langchain_tool.py        # LangChain search tool wrapper
│   ├── security/
│   │   └── middleware.py            # Security headers, rate limiting, audit log
│   └── tasks/
│       └── task_manager.py          # MCP task client manager (Calendar/Reminders)
├── frontend/
│   ├── src/
│   │   ├── api/                     # Typed API clients (chat, analytics, mcp, news)
│   │   ├── components/
│   │   │   ├── ChatInterface.tsx     # Main chat with file upload integration
│   │   │   ├── MessageInput.tsx      # Input box with attach, drag-drop, toolbar
│   │   │   ├── MessageList.tsx       # Messages with attachment badges
│   │   │   ├── SearchHistoryPanel.tsx# Search history side pane
│   │   │   ├── MCPServersPage.tsx    # MCP client server manager UI
│   │   │   ├── NewsPage.tsx          # News feed browser
│   │   │   └── LoginPage.tsx         # Auth login/register form
│   │   ├── contexts/                # Theme context
│   │   ├── hooks/
│   │   │   └── useSearchHistory.ts  # localStorage search history hook
│   │   ├── App.tsx                  # Root component & routing
│   │   └── main.tsx                 # Entry point
│   ├── package.json
│   ├── vite.config.ts
│   └── tailwind.config.js
├── mcp_clients/
│   ├── mcp_calendar_macos.py        # macOS Calendar MCP task client
│   └── mcp_reminders_macos.py       # macOS Reminders MCP task client
├── scripts/
│   └── ingest_documents.py          # CLI document ingestion
├── demo.py                          # Interactive CLI demo
├── mcp_stdio.py                     # Headless MCP stdio server entry point
├── run_server.py                    # Backend server entry point
├── start.sh                         # One-command startup (backend + frontend)
├── requirements.txt                 # Python dependencies
└── LICENSE                          # MIT License
```

---

## Troubleshooting

### Ollama Issues

| Problem | Solution |
|---|---|
| Models not loading | Run `ollama list` to verify. Pull missing models with `ollama pull <model>` |
| Ollama not running | Start with `ollama serve` or launch the Ollama app |
| Out of memory | Use smaller models, reduce `max_tokens`, or remove fallback model |

### Backend Issues

| Problem | Solution |
|---|---|
| Port 8000 in use | Change `server.port` in `config.yaml` or kill the process: `lsof -i :8000` |
| Import errors | Ensure venv is activated: `source venv/bin/activate` |
| Slow responses | Reduce `max_tokens`, use a smaller model, close other apps |

### Frontend Issues

| Problem | Solution |
|---|---|
| `npm install` fails | Delete `node_modules` and `package-lock.json`, then retry |
| Port 5173 in use | Kill the process: `lsof -i :5173` |
| API connection errors | Ensure backend is running. Check CORS in `config.yaml` |

### RAG Issues

| Problem | Solution |
|---|---|
| No results | Ingest documents first: `python scripts/ingest_documents.py data/documents/` |
| Poor results | Adjust `chunk_size` (500-1000 recommended) and `top_k` in config |

### Logs

Logs are written to `logs/chatbot.log`. Adjust the level in config:

```yaml
logging:
  level: "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
```

---

## Contributing

Contributions are welcome! Here's how to get started:

1. **Fork** the repository
2. **Create a branch**: `git checkout -b feature/your-feature`
3. **Make your changes** and test them
4. **Commit**: `git commit -m "Add your feature"`
5. **Push**: `git push origin feature/your-feature`
6. **Open a Pull Request**

### Guidelines

- Follow existing code style and patterns
- Add tests for new features where applicable
- Update documentation for user-facing changes
- Keep commits focused and well-described

---

## License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

You are free to use, modify, and distribute this software for any purpose, including commercial use.

---

## Acknowledgments

- [Ollama](https://ollama.com) — Local LLM runtime
- [LangChain](https://langchain.com) — LLM orchestration framework
- [FastAPI](https://fastapi.tiangolo.com) — Backend web framework
- [MCP SDK](https://github.com/modelcontextprotocol/python-sdk) — Model Context Protocol (mcp==1.17.0)
- [React](https://react.dev) + [Vite](https://vitejs.dev) — Frontend framework
- [Tailwind CSS](https://tailwindcss.com) — Utility-first CSS
- [DuckDuckGo](https://duckduckgo.com) — Web search & news API
- [Plotly](https://plotly.com) — Interactive charting
- [scikit-learn](https://scikit-learn.org) — Machine learning
- [python-jose](https://python-jose.readthedocs.io) — JWT token generation & validation
- [passlib](https://passlib.readthedocs.io) — Bcrypt password hashing
- [slowapi](https://slowapi.readthedocs.io) — Rate limiting middleware
- [python-docx](https://python-docx.readthedocs.io) — DOCX file processing
- [Pillow](https://pillow.readthedocs.io) — Image processing & metadata
- [mutagen](https://mutagen.readthedocs.io) — Audio metadata extraction
- [pandas](https://pandas.pydata.org) — Excel/CSV data loading
- [aiofiles](https://github.com/Tinche/aiofiles) — Async file I/O
