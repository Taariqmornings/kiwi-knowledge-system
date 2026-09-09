# Changelog

All notable changes to **Kiwi — Offline Knowledge Base System** are documented here.  
This project follows [Semantic Versioning](https://semver.org/).

---

## [1.2.0] — 2026-09-09

### Security
- **Fixed path traversal / arbitrary local file read** in the article and media endpoints. Entry paths are now validated before any disk access (`backend/app/services/extractor_service.py`), so a crafted URL can no longer escape the extraction store.
- **Restricted CORS** on article, media, and chat-stream responses to the app's own origins instead of `*` (`backend/app/api/articles.py`, `backend/app/api/chat.py`) — third-party pages can no longer read local content off the API.
- **HTML-escaped all interpolated values** in the reader and empty-state pages (`transformer_service.py`), closing reflected/stored XSS from article-derived titles and request data.
- **Hardened the Electron shell**: `webSecurity` is now enabled, `nodeIntegration` stays off, renderers are sandboxed, `window.open`/`will-navigate` are restricted to the local backend (external links open in the system browser), and `postMessage` handlers verify the sender origin.
- **Removed raw exception text** from API error responses (`chat.py`, `articles.py`) — details are logged server-side only.

### CI & Quality
- **Frontend `npm run lint` now passes** (23 previously-failing React Hooks / `no-empty` / fast-refresh issues fixed).
- **Backend test suite is green** (38 tests) — the pagination test fixture now matches the app's content-length filter.
- **CI installs `libzim`** for the backend job instead of stripping it (it ships Linux wheels) — the backend job previously failed at collection.
- **Alembic migrations now target the app's real `DATABASE_PATH`** instead of a working-directory-relative default (`alembic/env.py`).
- Frontend `build` no longer emits a >1 MB chunk warning: vendor libraries are code-split (`vite.config.ts`) and `highlight.js` loads a focused language subset.

### Packaging & Branding
- Unified identity: `package.json` is now `kiwi` v1.1.0 with `productName: "Kiwi"`, a proper `appId`, `author`, and `license`; the in-app version string reads from a single source.
- Added a proper PNG app icon (`frontend/build/icon.png`) for Electron packaging (SVG icons are not supported by electron-builder).
- Packaged desktop builds now **exclude the local database, tests, and caches** from `extraResources`.
- Frontend README rewritten (was the default Vite template), dead scaffold assets and components removed, favicon fixed, and meaningful API-client tests added.

### Docs & Repo
- Added `SECURITY.md`, `CODE_OF_CONDUCT.md`, `.gitattributes`, and `.editorconfig`.
- Backend startup logs now use `logging` instead of `print()`.
- `VITE_BACKEND_URL` documented for browser-mode deployments.

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
