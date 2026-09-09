# Kiwi — Offline Knowledge Base System

> Index compressed ZIM archives, search hundreds of thousands of articles in under 100 ms, and chat with your local knowledge base using a private on-device AI — all with zero internet dependency.

Created and maintained by **[Taariq Ebrahim](https://github.com/Taariqmornings)**.

[![Author](https://img.shields.io/badge/Author-Taariq%20Ebrahim-0ea5e9.svg)](https://github.com/Taariqmornings)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![CI](https://github.com/Taariqmornings/kiwi-knowledge-system/actions/workflows/ci.yml/badge.svg)](https://github.com/Taariqmornings/kiwi-knowledge-system/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776ab.svg)](#prerequisites)
[![Node.js](https://img.shields.io/badge/Node.js-20.19%2B-339933.svg)](#prerequisites)
[![React](https://img.shields.io/badge/React-19-61dafb.svg)](#tech-stack)

---

## What is Kiwi?

Kiwi is a desktop application that lets you turn offline [ZIM archives](https://wiki.kiwix.org/wiki/Content_in_all_languages) (Wikipedia, StackExchange, DevDocs, medical references, and more) into a fast, searchable personal knowledge base — with an optional local AI chat assistant that never touches the internet.

```
┌─────────────────────────────────────────────────────────┐
│  Kiwi  │ Search  │ Archives  │ Chat  │ Settings          │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  🔍  Search your offline archives...        [Ctrl+K]    │
│                                                         │
│  Photosynthesis  ·  Wikipedia EN                        │
│  The process by which plants convert light to energy…   │
│                                                         │
│  Python (programming language)  ·  DevDocs              │
│  High-level general-purpose language created by…        │
│                                                         │
│  Quantum Mechanics  ·  Wikipedia EN                     │
│  Fundamental theory in physics describing nature at…    │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## Features

- **Full-text search** — SQLite FTS5 with BM25 ranking returns results in under 100 ms across millions of indexed articles
- **ZIM archive support** — directly reads `.zim` files from Wikipedia, StackExchange, DevDocs, and any other Kiwix-compatible archive
- **Modern article reader** — transforms raw ZIM HTML into a clean, readable page with auto-generated table of contents, image lightbox, and code copy buttons
- **Offline AI chat (optional)** — RAG pipeline retrieves relevant articles and streams answers from a local [Ollama](https://ollama.com) model; works without internet
- **Multi-tab browsing** — open and cross-reference multiple articles simultaneously
- **Background indexing** — indexes archives in a background thread with live progress; survives restarts via a persistent job table
- **Command palette** — `Ctrl+K` for instant navigation
- **Electron desktop app** — runs as a native application on Windows, macOS, and Linux
- **Browser mode** — also runs in any browser without Electron (no file picker, everything else works)

---

## Tech Stack

| Layer | Technology |
|---|---|
| Desktop shell | Electron 30 |
| Frontend | React 19, TypeScript, Vite, Tailwind CSS 4 |
| Backend API | FastAPI, Uvicorn |
| Database | SQLite (WAL mode) + FTS5 full-text index |
| ORM / migrations | SQLAlchemy 2.0, Alembic |
| ZIM parsing | python-libzim |
| Local AI | Ollama (any model — default: `gemma3:1b`) |

---

## Architecture

```
┌─────────────────────────────────────────┐
│  Electron (desktop shell)               │
│  ┌───────────────────────────────────┐  │
│  │  React 19  ·  Vite  ·  TypeScript │  │
│  │  Search · Reader · Chat · Archives│  │
│  └──────────────┬────────────────────┘  │
└─────────────────│───────────────────────┘
                  │ HTTP / SSE
┌─────────────────▼───────────────────────┐
│  FastAPI  (port 8000)                   │
│  ┌──────────┐  ┌──────────┐  ┌───────┐ │
│  │ Search   │  │ Articles │  │  Chat │ │
│  │ FTS5/BM25│  │ ZIM → HTML│  │  RAG │ │
│  └──────────┘  └──────────┘  └───┬───┘ │
└───────────────────────────────────│─────┘
          │                         │
┌─────────▼──────┐      ┌──────────▼────┐
│ SQLite         │      │ Ollama daemon │
│ knowledge.db   │      │ (optional)    │
│ articles + FTS │      │ gemma3:1b     │
└────────────────┘      └───────────────┘
          │
┌─────────▼──────┐
│ .zim files     │
│ (local disk)   │
└────────────────┘
```

---

## Quick Start — Try it in 5 minutes (no ZIM files needed)

This path seeds the database with 30 sample articles so you can explore the full UI immediately.

```bash
# 1. Clone the repository
git clone https://github.com/Taariqmornings/kiwi-knowledge-system.git
cd kiwi-knowledge-system

# 2. Install backend dependencies
cd backend
python -m venv venv

# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt

# 3. Run database migrations (creates the SQLite database)
alembic upgrade head

# 4. Seed demo articles (no ZIM file required)
python scripts/seed_demo.py

# 5. Start the backend
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# 6. In a separate terminal — install and start the frontend
cd ../frontend
npm install
npm run dev

# 7. Open http://localhost:5173 in your browser
```

Search for terms like **photosynthesis**, **python**, **quantum**, **gravity**, or **Shakespeare** to see results immediately.

> **See it in action:** [`docs/DEMO.md`](docs/DEMO.md) contains verified output from a live instance running against **1.1 million indexed articles** — including real search results and an offline AI chat answer with citations — plus a script for recording your own walkthrough.

---

## Full Installation (with real ZIM files)

### Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Python | 3.10+ | Must be in `PATH` |
| Node.js | 20.19+ | Includes `npm` |
| Git | any | — |
| Ollama | latest | **Optional** — only needed for AI chat |

### Step 1 — Clone

```bash
git clone https://github.com/Taariqmornings/kiwi-knowledge-system.git
cd kiwi-knowledge-system
```

### Step 2 — Configure environment

```bash
cp .env.example .env
```

Open `.env` and set any values you want to override. At minimum, the defaults work out of the box. See [Environment Variables](#environment-variables) below for a full reference.

### Step 3 — Get ZIM archives (optional but recommended)

Download any `.zim` file from [https://download.kiwix.org/zim/](https://download.kiwix.org/zim/) and place it in a folder on your machine. Good starting points:

- `wikipedia_en_simple_all_nopic` — Simple English Wikipedia (~1 GB, manageable)
- `stackoverflow.com_en_all` — Stack Overflow archive
- `devdocs.io_en_all` — Developer documentation

### Step 4 — Launch

**Windows (recommended — handles everything automatically):**

```cmd
# Production mode
start.bat

# Development mode (hot reload for backend + frontend)
start.bat -Dev
```

The launcher script:
- Creates and provisions the Python virtual environment automatically
- Installs Node dependencies if missing
- Runs database migrations
- Starts the FastAPI backend and Vite dev server
- Launches the Electron desktop window

**macOS / Linux (manual start):**

```bash
# Terminal 1 — backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# Terminal 2 — frontend (browser mode — no Electron required)
cd frontend
npm install
npm run dev
# Open http://localhost:5173
```

### Step 5 — Index your ZIM files

1. Open the **Archives** tab in the app
2. Click **Browse** (Electron) or enter the directory path manually
3. Click **Scan** — Kiwi finds all `.zim` files automatically
4. Click **Index** on each archive — background indexing starts immediately

### Step 6 — Search

Switch to the **Search** tab and start typing. Results appear instantly once indexing is complete.

---

## Environment Variables

Copy `.env.example` to `.env` — all variables are optional with sensible defaults.

| Variable | Default | Description |
|---|---|---|
| `DATABASE_PATH` | `backend/data/knowledge.db` | Path to the SQLite database file |
| `OLLAMA_HOST` | `http://127.0.0.1:11434` | URL of your local Ollama daemon |
| `OLLAMA_MODEL` | `gemma3:1b` | Model name to use for AI chat (must be pulled first) |
| `INDEX_BATCH_SIZE` | `1000` | Articles committed per batch during indexing |
| `MAX_SUMMARY_LENGTH` | `500` | Max characters stored in the article summary field |
| `MAX_REQUEST_SIZE_MB` | `50` | Max incoming request body size |
| `RATE_LIMIT_PER_MINUTE` | `60` | API rate limit per IP |
| `KIWI_FORCE_DEV` | `0` | Set to `1` to force Electron to load the Vite dev server |

**Frontend-only variable** (set in `frontend/.env`, used by the Vite build):

| Variable | Default | Description |
|---|---|---|
| `VITE_BACKEND_URL` | `http://127.0.0.1:8000` | Backend URL used in **browser mode** (the Electron app gets its URL via IPC) |

---

## AI Chat Setup (Optional)

The chat sidebar uses a local [Ollama](https://ollama.com) model. No API key or internet connection required.

```bash
# 1. Install Ollama from https://ollama.com

# 2. Start the Ollama daemon
ollama serve

# 3. Pull a model (pick any that fits your hardware)
ollama pull gemma3:1b        # ~900 MB  — fast, good for most queries
ollama pull llama3.2:3b      # ~2 GB    — better reasoning
ollama pull phi3:mini        # ~2.3 GB  — Microsoft's efficient model

# 4. Set the model in your .env (if not using the default)
# OLLAMA_MODEL=llama3.2:3b
```

If Ollama is not running, all search and article browsing features still work normally. Only the chat sidebar will be disabled.

---

## API Reference

The FastAPI backend exposes a REST + SSE API at `http://localhost:8000`.

Interactive docs available at: **`http://localhost:8000/docs`** (Swagger UI)

### Key endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/search/query?q=...` | Full-text BM25 search with pagination |
| `GET` | `/api/search/all` | Browse all indexed articles |
| `GET` | `/api/search/autocomplete?q=...` | Instant title suggestions |
| `GET` | `/api/search/categories` | List browse categories |
| `GET` | `/api/search/categories/{id}/articles` | Browse articles by category |
| `GET` | `/api/archives` | List all registered ZIM archives |
| `POST` | `/api/archives/scan` | Scan a directory for ZIM files |
| `POST` | `/api/archives/{id}/index/start` | Start background indexing |
| `GET` | `/api/archives/{id}/index/stream` | SSE stream of indexing progress |
| `GET` | `/api/articles/{id}/view/{path}` | Render an article as modern HTML |
| `POST` | `/api/chat/ask` | SSE stream of AI chat response |
| `GET` | `/api/health` | Backend health + stats |

---

## Project Structure

```
kiwi-knowledge-system/
├── .github/
│   ├── assets/              # Banner and screenshots
│   ├── ISSUE_TEMPLATE/      # Bug report and feature request templates
│   ├── PULL_REQUEST_TEMPLATE.md
│   └── workflows/
│       └── ci.yml           # GitHub Actions CI
│
├── backend/
│   ├── alembic/             # Database schema migrations
│   ├── app/
│   │   ├── api/             # FastAPI route handlers
│   │   │   ├── archives.py  # ZIM archive management
│   │   │   ├── articles.py  # Article rendering
│   │   │   ├── chat.py      # AI chat / RAG
│   │   │   ├── search.py    # FTS5 search & browse
│   │   │   └── settings.py  # Persisted app settings
│   │   ├── core/
│   │   │   ├── config.py    # All configuration & env vars
│   │   │   └── database.py  # SQLAlchemy engine & session
│   │   ├── models/
│   │   │   └── schemas.py   # Pydantic request/response models
│   │   ├── services/
│   │   │   ├── archive_service.py    # ZIM file scanning
│   │   │   ├── indexer_service.py    # Background article indexer
│   │   │   ├── job_registry.py       # Persistent job state
│   │   │   ├── llm_service.py        # Ollama streaming client
│   │   │   ├── rag_service.py        # Retrieval-augmented generation
│   │   │   ├── search_service.py     # BM25 / FTS5 query engine
│   │   │   └── transformer_service.py # ZIM HTML → modern HTML
│   │   └── main.py          # FastAPI app, lifespan, middleware
│   ├── scripts/
│   │   └── seed_demo.py     # Seed 30 sample articles for demo
│   ├── tests/               # pytest test suite
│   └── requirements.txt
│
├── frontend/
│   ├── electron/
│   │   ├── main.js          # Electron main process
│   │   └── preload.js       # Context bridge (IPC)
│   ├── src/
│   │   ├── components/      # React components
│   │   ├── context/         # Global app state (AppContext)
│   │   ├── hooks/           # Custom React hooks
│   │   ├── services/
│   │   │   └── api.ts       # Typed API client
│   │   └── types/
│   │       └── index.ts     # TypeScript interfaces
│   ├── index.html
│   ├── package.json
│   └── vite.config.ts
│
├── .env.example             # Environment variable reference
├── .gitignore
├── CHANGELOG.md
├── CONTRIBUTING.md
├── LICENSE                  # MIT
├── start.bat                # Windows launcher (CMD wrapper)
└── start.ps1                # Windows launcher (PowerShell — handles everything)
```

---

## Running Tests

```bash
# Backend (pytest)
cd backend
source venv/bin/activate   # or venv\Scripts\activate on Windows
pytest tests/ -v

# Frontend (Vitest)
cd frontend
npm run test
```

---

## Building for Distribution

```bash
cd frontend

# Build production frontend bundle
npm run build

# Package as a native desktop installer
npm run electron:pack
```

Output is placed in `frontend/release/`. Supported targets:
- **Windows** — `.exe` NSIS installer + portable `.exe`
- **macOS** — `.dmg`
- **Linux** — `.AppImage`

---

## Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) for:

- Development environment setup
- Coding standards (Python PEP 8, strict TypeScript)
- Branch naming and commit message conventions
- How to run the test suite before submitting a PR

For bugs, use the [Bug Report](.github/ISSUE_TEMPLATE/bug_report.md) template.  
For ideas, use the [Feature Request](.github/ISSUE_TEMPLATE/feature_request.md) template.

---

## Roadmap

- [x] Full-text BM25 search over ZIM archives
- [x] Background indexing with persistent job tracking
- [x] Local RAG AI chat via Ollama
- [x] Multi-tab article reader with browser history
- [x] Command palette (`Ctrl+K`)
- [x] Electron desktop app (Windows / macOS / Linux)
- [ ] Fuzzy / Levenshtein fallback search tier
- [ ] Bookmarks sync and export
- [ ] Article annotation and highlights
- [ ] Split ZIM file support
- [ ] CI-built binary releases

---

## License

Distributed under the **MIT License**. See [LICENSE](LICENSE) for details.

---

## Author

**Kiwi is built and maintained by [Taariq Ebrahim](https://github.com/Taariqmornings)** — a software engineer based in Mbombela, South Africa, focused on software, AI systems and offline-capable softwares.

Taariq is the founder of **Chatterbolic Solutions**, a software company specialising in AI automation and custom systems. Kiwi is an open-source project authored by Taariq under the Chatterbolic banner.

- **GitHub:** [@Taariqmornings](https://github.com/Taariqmornings)
- **Company:** [chatterbolic.co.za](https://chatterbolic.co.za)

If you build something with Kiwi or want to collaborate, feel free to reach out or open an issue.
