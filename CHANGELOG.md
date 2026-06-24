# Changelog

All notable changes to the **Kiwi: Offline Knowledge OS** project will be documented in this file. This project adheres to Semantic Versioning (`vMAJOR.MINOR.PATCH`).

---

## [1.0.0] - 2026-05-29
This is the official stable release of **Kiwi**, representing a production-grade local knowledge indexing and RAG-enabled AI search desktop application.

### Added
- **Ollama Gemma 3 integration**: Full offline retrieval-augmented generation (RAG) capabilities using local loopback HTTP calls to Ollama daemon (`gemma3:1b`).
- **Deferred Startup Indexing**: Defer directory scanning and database indexing for 5 seconds on startup to allow React frontend's initial API fetches to complete without GIL bottlenecks.
- **Auto-detection of ZIM files**: Scan directories and automatically register valid ZIM archives to index.
- **Comprehensive Community Templates**: Added issue templates, PR checklists, and developer setup documentation for collaborative scaling.

### Changed
- **Performance Tuning**: Refactored SQLite pragmas. Switched to `journal_mode=WAL` (Write-Ahead Logging) and `synchronous=NORMAL` to enable concurrent reads while building the full-text search index.
- **Robust SQLite Busy Handlers**: Configured `busy_timeout=30000` (30 seconds) to prevent locked database errors under heavy indexing.

### Fixed
- **FTS5 Drift Safety**: Implemented programmatically dropped and recreated database triggers (`articles_ai`, `articles_ad`, `articles_au`) during startup checkups to prevent synchronization drift crashes.
- **Duplicate Cleanups**: Added automatic startup cleanup task that deduplicates the database index by keeping the lowest unique ID per `(archive_id, path)`.

---

## [0.9.0] - 2026-02-15
Initial beta release of Kiwi offline knowledge platform.

### Added
- **FastAPI Backend Server**: Structured API endpoints for serving articles, listing registered archives, and fetching health statistics.
- **Vite & React Frontend**: Beautiful web UI featuring full-text search layout, sidebar, and direct offline article reader.
- **Electron Container**: Integrated desktop shell using Electron wrapping to run backend and frontend locally in a single workspace.
- **ZIM File Parsing**: Integrated `libzim` Python bindings to directly access compressed ZIM archives.
