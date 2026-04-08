# RAGenie

An open-source AI assistant powered by **Retrieval-Augmented Generation (RAG)** with local LLMs, internet search, multi-model orchestration, and data analytics — all running on your own hardware.

![Python](https://img.shields.io/badge/Python-3.9+-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green?logo=fastapi)
![React](https://img.shields.io/badge/React-18-blue?logo=react)
![Ollama](https://img.shields.io/badge/Ollama-Local%20LLMs-black?logo=ollama)
![License](https://img.shields.io/badge/License-MIT-yellow)

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
- **MCP Support** — Model Context Protocol server/client for integration with tools like Claude Desktop.
- **Fully Configurable** — Single YAML file controls LLM settings, RAG parameters, search behavior, server config, and more.

---

## How It Works

RAGenie is a self-hosted AI assistant that combines four core capabilities — **chat**, **document knowledge**, **web search**, and **data analytics** — into a single application. Everything runs locally; no data leaves your machine.

### Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    React Frontend                        │
│  Chat UI  │  Analytics Dashboard  │  Document Sidebar    │
└─────┬──────────────┬───────────────────┬────────────────┘
      │ WebSocket    │ REST              │ REST
      ▼              ▼                   ▼
┌─────────────────────────────────────────────────────────┐
│                  FastAPI Backend                          │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │    Chat       │  │  Analytics   │  │   Document    │  │
│  │ Orchestrator  │  │   Engine     │  │  Management   │  │
│  └──────┬───────┘  └──────┬───────┘  └───────┬───────┘  │
│         │                 │                   │          │
│  ┌──────▼───────┐  ┌──────▼───────┐  ┌───────▼───────┐  │
│  │ Multi-Model  │  │  Visualizer  │  │  Ingestion    │  │
│  │   Manager    │  │  (Plotly)    │  │  Pipeline     │  │
│  └──────┬───────┘  └──────────────┘  └───────┬───────┘  │
│         │                                     │          │
│  ┌──────▼───────────────────┐  ┌──────────────▼───────┐  │
│  │  RAG System (BM25)       │  │  Document Loaders    │  │
│  │  + Context Builder       │  │  (PDF/DOCX/Excel/    │  │
│  │                          │  │   Image/Audio/TXT)   │  │
│  └──────────────────────────┘  └──────────────────────┘  │
│         │                                                │
│  ┌──────▼───────────────────┐                            │
│  │  Search Service          │                            │
│  │  (DuckDuckGo + Cache)    │                            │
│  └──────────────────────────┘                            │
└─────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────┐
│   Ollama (Local)     │
│  ┌───────────────┐   │
│  │ Reasoning LLM │   │
│  │ Main LLM      │   │
│  │ Fallback LLM  │   │
│  └───────────────┘   │
└──────────────────────┘
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

- [How It Works](#how-it-works)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Configuration](#configuration)
- [Multi-Model Setup](#multi-model-setup)
- [Document Management](#document-management)
- [Analytics](#analytics)
- [API Reference](#api-reference)
- [Frontend](#frontend)
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

## Frontend

The frontend is built with **React 18 + TypeScript + Vite + Tailwind CSS**.

### Features

- Real-time chat with WebSocket streaming
- **In-chat file upload** — attach files via 📎 button or drag-and-drop, with file preview chips
- **Search history pane** — side panel with filtering, query reuse, and clear controls (localStorage-persisted)
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
│   └── config.yaml              # All application settings
├── data/
│   ├── documents/               # Uploaded/ingested documents
│   ├── index/                   # RAG index (page_index.json)
│   └── conversations.db         # Conversation history (SQLite)
├── src/
│   ├── api/
│   │   ├── app.py               # FastAPI application & REST routes
│   │   ├── websocket.py         # WebSocket streaming handler
│   │   └── analytics_routes.py  # Analytics API endpoints
│   ├── analytics/
│   │   ├── data_loader.py       # Multi-format data parser
│   │   ├── analytics_engine.py  # Statistical analysis & ML models
│   │   └── visualizer.py        # Plotly chart generation
│   ├── chat/
│   │   └── orchestrator.py      # Chat orchestration & agent logic
│   ├── config/
│   │   ├── models.py            # Pydantic config models
│   │   └── loader.py            # YAML config loader
│   ├── core/
│   │   ├── models.py            # Data models (Document, Chunk, etc.)
│   │   ├── document_store.py    # Storage interface
│   │   ├── exceptions.py        # Custom exceptions
│   │   └── logging_config.py    # Logging setup
│   ├── ingestion/
│   │   ├── loaders.py           # Document loaders (PDF/DOCX/Excel/Image/Audio/TXT/MD)
│   │   └── pipeline.py          # Ingestion pipeline
│   ├── llm/
│   │   ├── langchain_wrapper.py # LangChain LLM integration
│   │   ├── multi_model_manager.py # Multi-model orchestration
│   │   ├── ollama_wrapper.py    # Ollama provider
│   │   ├── model_loader.py      # HuggingFace model loader
│   │   └── prompts.py           # System & RAG prompt templates
│   ├── rag/
│   │   ├── page_index_store.py  # BM25 index & search
│   │   ├── chunker.py           # Document chunking
│   │   ├── retriever.py         # LangChain retriever adapter
│   │   └── context_builder.py   # Context augmentation
│   └── search/
│       ├── search_service.py    # DuckDuckGo search
│       └── langchain_tool.py    # LangChain search tool
├── frontend/
│   ├── src/
│   │   ├── api/                 # API client (chat, analytics)
│   │   ├── components/          # React components
│   │   │   ├── ChatInterface.tsx    # Main chat with file upload integration
│   │   │   ├── MessageInput.tsx     # Input box with attach, drag-drop, toolbar
│   │   │   ├── MessageList.tsx      # Messages with file attachment badges
│   │   │   └── SearchHistoryPanel.tsx # Search history side pane
│   │   ├── contexts/            # Theme context
│   │   ├── hooks/
│   │   │   └── useSearchHistory.ts   # localStorage search history hook
│   │   ├── App.tsx              # Root component
│   │   └── main.tsx             # Entry point
│   ├── package.json
│   ├── vite.config.ts
│   └── tailwind.config.js
├── scripts/
│   └── ingest_documents.py      # CLI document ingestion
├── demo.py                      # Interactive CLI demo
├── run_server.py                # Backend server entry point
├── start.sh                     # One-command startup script
├── requirements.txt             # Python dependencies
└── LICENSE                      # MIT License
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
- [React](https://react.dev) + [Vite](https://vitejs.dev) — Frontend framework
- [Tailwind CSS](https://tailwindcss.com) — Utility-first CSS
- [DuckDuckGo](https://duckduckgo.com) — Search API
- [Plotly](https://plotly.com) — Interactive charting
- [scikit-learn](https://scikit-learn.org) — Machine learning
- [python-docx](https://python-docx.readthedocs.io) — DOCX file processing
- [Pillow](https://pillow.readthedocs.io) — Image processing & metadata
- [mutagen](https://mutagen.readthedocs.io) — Audio metadata extraction
- [pandas](https://pandas.pydata.org) — Excel/CSV data loading
