# Changelog

All notable changes to **Kiwi — Offline Knowledge Base System** are documented here.  
This project follows [Semantic Versioning](https://semver.org/).

---

## [1.1.0] — 2026-06-25

### Added
- **`GET /api/search/all`** — new endpoint returns all indexed articles across every archive with pagination; provides a guaranteed path to content regardless of auto-categorisation
- **Browse All Articles button** in the Search panel — visible when indexed archives are present and no search query is active
- **Demo seed script** (`backend/scripts/seed_demo.py`) — populates the database with 30 sample articles covering science, history, technology, and more; lets new users explore the full UI without downloading ZIM files
- **`.env.example`** — comprehensive reference for every configurable environment variable with safe defaults and setup instructions
- **`OLLAMA_HOST` and `OLLAMA_MODEL` environment variables** — previously hardcoded values in `llm_service.py` are now fully configurable; Ollama connection details no longer require source code changes
- **`DATABASE_PATH`, `INDEX_BATCH_SIZE`, `MAX_SUMMARY_LENGTH`, `MAX_REQUEST_SIZE_MB`, `RATE_LIMIT_PER_MINUTE` environment variables** — all previously hardcoded constants in `config.py` can now be overridden without touching source code

### Changed
- `config.py` rewritten to read every tunable value from environment variables with sensible defaults
- `llm_service.py` reads `OLLAMA_HOST` and `OLLAMA_MODEL` from the environment instead of using hardcoded strings
- CI workflow (`.github/workflows/ci.yml`) fixed: `working-directory` paths corrected from `knowledge-system/frontend` → `frontend` (broken since initial commit); spurious `node-size` key removed; now tests against Node 18 and 20, Python 3.10/3.11/3.12
- `README.md` rewritten: added 5-minute quick start, browser-only mode instructions, full environment variable table, API reference table, project structure diagram, and AI chat setup guide; removed `<repository-url>` placeholder

### Fixed
- CI was completely broken due to wrong `working-directory` paths referencing a non-existent parent folder
- `libzim` excluded from CI pip install (no Linux wheel available on all Python versions); remaining stack still validated

---

## [1.0.0] — 2026-05-29

### Added
- **Ollama Gemma 3 integration** — full offline RAG chat using local loopback HTTP calls to the Ollama daemon (`gemma3:1b` default)
- **Deferred startup indexing** — background indexing deferred 5 s to allow React frontend queries to resolve before the GIL is occupied
- **Persistent IndexJob table** — background job state survives server restarts; in-flight jobs auto-marked as `failed` on next startup
- **Archive auto-categorisation** — ZIM filenames are matched against keyword lists to auto-assign category tags
- **Community templates** — GitHub issue templates, PR checklist, CONTRIBUTING.md

### Changed
- SQLite tuned with `journal_mode=WAL`, `synchronous=NORMAL`, and `busy_timeout=30000` for concurrent read/write performance during indexing

### Fixed
- FTS5 trigger drift prevention — triggers are dropped and recreated on startup to prevent sync crashes
- Duplicate article deduplication on startup via `(archive_id, path)` unique constraint

---

## [0.9.0] — 2026-02-15

### Added
- FastAPI backend with article, archive, search, and settings endpoints
- React 19 + TypeScript + Vite frontend
- Electron shell container
- SQLite FTS5 full-text search index
- ZIM file parsing via `python-libzim`
- BM25 field-boosted search (title 5×, keywords 3×, summary 1×) with 4-tier typo-tolerant fallback
- Background article indexer with SSE progress streaming
- Alembic database migrations
- Multi-tab article reader with browser history
- Bookmarks stored in `localStorage`
- Electron IPC handlers for native directory picker, backend URL, and status events
- PowerShell launcher script (`start.ps1`) with smart pip-install hashing, port cleanup, and dev/production modes
