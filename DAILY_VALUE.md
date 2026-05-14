# RAGenie — Your Personal AI That Works For You Every Day

> A self-hosted AI assistant that removes the repetitive, slow, and fragmented parts of your daily knowledge work — without sending a single byte to the cloud.

---

## The Problem RAGenie Solves

Every day you probably face some combination of these:

- 🔍 **Searching for something you already read** — that PDF report, that contract clause, that meeting note — buried somewhere on your disk.
- 🌐 **Switching between browser tabs** to cross-reference live information with your own documents.
- 📊 **Opening Excel, writing formulas, running pivot tables** just to get a quick statistical summary of a dataset.
- 📰 **Manually scanning news sites** to stay updated on topics that matter to your work.
- 🔄 **Repeating the same context** to every AI chatbot you open — they forget you the moment you close the tab.
- 🔒 **Worrying about what you upload** to ChatGPT or Gemini — confidential reports, personal data, internal strategy docs.

RAGenie is built to eliminate every one of these frictions.

---

## What RAGenie Does For You, Concretely

### 1 — Answers questions from your own documents instantly

You upload your files once. After that, you just ask:

> *"What were the key findings in the Q3 risk assessment report?"*
> *"What is the notice period clause in the Rajan contract?"*
> *"Summarise all the action items from the board meeting notes."*

RAGenie reads your PDFs, Word documents, spreadsheets, images, and even audio files — chunks them, indexes them, and retrieves the right passage for every question. No browsing, no `Ctrl+F`, no re-reading the whole document.

**Time saved:** 15–30 minutes per day of document hunting.

---

### 2 — Combines your documents with live web information

Instead of opening a document in one tab and Google in another, RAGenie blends both in a single answer:

> *"Based on my investment policy document, how does the current RBI rate change affect my portfolio strategy?"*
> *"Compare my existing vendor contract terms against what competitors are currently offering."*

It fetches real-time web results, merges them with your local knowledge base, and gives you one coherent, cited answer.

**Time saved:** Eliminates the mental overhead of context-switching between multiple sources.

---

### 3 — Becomes your personal data analyst

Upload any CSV, Excel, or JSON file and ask natural-language questions:

> *"Is there a correlation between marketing spend and revenue in this dataset?"*
> *"Which months have the most outliers in the sales figures?"*
> *"Predict the trend for the next 6 months."*

RAGenie runs statistical analysis, builds regression models, detects outliers, and generates interactive charts — all from a single upload. No Python scripts, no formulas, no pivot tables.

**Time saved:** Hours of manual data wrangling per report.

---

### 4 — Keeps you briefed on topics you care about — automatically

You tell RAGenie what topics matter to you (e.g. *"IPL"*, *"AI regulation"*, *"West Bengal politics"*). Every hour it fetches news, scrapes the full articles, and summarises them using the LLM.

Every morning you get a **daily briefing** in your chat — a digest of everything relevant that happened overnight, waiting for you when you open the app.

> No RSS readers. No email newsletters. No doomscrolling.

**Time saved:** 20–40 minutes of morning news browsing, compressed into a 2-minute read.

---

### 5 — Remembers you across every conversation

Most AI assistants forget you the moment you close the tab. RAGenie stores important context from your conversations permanently:

- Your preferences, working style, and recurring topics.
- Decisions you've made and context you've shared.
- Past questions and how they were answered.

Every new conversation starts informed. You never have to re-explain who you are or what you're working on.

> *"Remember I'm building a FastAPI app with JWT auth and Ollama."*
> Next week: *"How should I add rate limiting?"* — it already knows your stack.

**Time saved:** The 2–5 minutes of context-setting at the start of every AI session.

---

### 6 — Connects to your tools via MCP — one agent for everything

RAGenie acts as an MCP client, connecting to hundreds of third-party tools. From a single chat interface you can:

- **Browse and write files** (via Filesystem MCP server)
- **Query databases, APIs, statistics** (via MoSPI, custom servers)
- **Add Calendar events / Reminders** on macOS
- **Connect any MCP-compatible tool** in the growing ecosystem

> *"Check the sales CSV in my Downloads folder and create a summary chart."*
> *"What are this week's economic indicators from the government data API?"*
> *"Remind me tomorrow at 9 AM to follow up with the client."*

One interface. Every tool.

**Time saved:** No more switching between apps to accomplish multi-step workflows.

---

### 7 — Gets smarter the more you use it

When RAGenie gives a great answer, click 👍. When it misses, click 👎. These ratings feed back into the retrieval system — over time it learns which kinds of answers and sources work best for **you specifically**, not for a generic user.

**Long-term benefit:** The assistant gradually adapts to your domain, vocabulary, and preferences.

---

### 8 — Everything stays on your machine. Always.

Every document you upload, every question you ask, every memory stored — stays on your computer. No cloud, no API calls to external LLM providers, no subscription fees.

This means:
- **Confidential documents are safe** — financials, legal contracts, internal strategy, personal data.
- **Works offline** once models are downloaded.
- **No monthly bill** — runs on your existing hardware.

---

## A Typical Day With RAGenie

| Time | Without RAGenie | With RAGenie |
|---|---|---|
| **8:00 AM** | Browse 4 news sites for 30 min | Read the auto-generated daily briefing in 2 min |
| **9:30 AM** | Hunt through PDFs for a clause | Ask RAGenie, get the exact paragraph instantly |
| **11:00 AM** | Spend 45 min building an Excel pivot table | Upload CSV, ask for analysis, get chart in 30 sec |
| **2:00 PM** | Open ChatGPT, re-explain your project context | RAGenie already knows — continue where you left off |
| **3:30 PM** | Switch between 5 browser tabs to cross-reference | Single query blends documents + live web |
| **5:00 PM** | Manually write a summary of today's research | Ask RAGenie to summarise the documents you shared |

**Estimated daily time saved: 1.5 – 3 hours.**

---

## Getting Started in 5 Minutes

```bash
# Clone and install
git clone https://github.com/ratulsarkar-iam/RAGenie.git
cd RAGenie
pip install -r requirements.txt

# Start (backend + frontend together)
./start.sh
```

Open **http://localhost:5173** → Upload a document → Start asking questions.

Full setup guide: [README.md](README.md)

---

## The One-Line Summary

> RAGenie is the AI assistant that knows your documents, reads your news, remembers your context, connects your tools, analyzes your data — and keeps everything private on your own machine.
