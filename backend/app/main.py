import logging
import time
import uvicorn
from collections import defaultdict
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from pathlib import Path

# Structured logging — timestamps + level + module on every line
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)  # quiet down per-request noise

from app.core.config import APP_NAME, VERSION, BASE_DIR, ALLOWED_ORIGINS, RATE_LIMIT_PER_MINUTE
from app.core.database import engine
from app.core import settings_store
from app.database_models import Category
from app.core.database import SessionLocal
from app.api import archives, search, articles, chat, health, settings as settings_api
from app.services import job_registry
from app.services.archive_service import ArchiveService
from app.services.indexer_service import IndexerService


def run_migrations():
    """Execute Alembic migrations programmatically on startup."""
    try:
        from alembic.config import Config
        from alembic import command

        alembic_cfg = Config(str(Path(BASE_DIR) / "alembic.ini"))
        command.upgrade(alembic_cfg, "head")
        print("[Migration] Database schema up to date.")
    except Exception as e:
        print(f"[Migration] Warning: {e}. Falling back to create_all.")
        from app.core.database import Base
        Base.metadata.create_all(bind=engine)


def seed_categories():
    """Seed default knowledge categories if they don't exist."""
    db = SessionLocal()
    try:
        default_categories = [
            {"name": "Medicine", "icon": "HeartPulse"},
            {"name": "Science", "icon": "Atom"},
            {"name": "Engineering", "icon": "Cpu"},
            {"name": "History", "icon": "BookOpen"},
            {"name": "Geography", "icon": "Globe"},
            {"name": "Coding", "icon": "Code"},
            {"name": "Mathematics", "icon": "Calculator"},
            {"name": "Survival", "icon": "Flame"},
            {"name": "Education", "icon": "GraduationCap"},
            {"name": "General Knowledge", "icon": "Library"},
        ]

        for item in default_categories:
            exists = db.query(Category).filter(Category.name == item["name"]).first()
            if not exists:
                db.add(Category(name=item["name"], icon=item["icon"]))

        db.commit()
        print("[Init] Categories seeded.")
    except Exception as e:
        print(f"[Init] Category seed failed: {e}")
        db.rollback()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on application startup and clean up on shutdown."""
    run_migrations()

    # Migration now owns FTS creation and triggers. The block below is a safety
    # net for environments where Alembic was not run (e.g. fresh dev install
    # without running migrations manually). It creates the content-backed table
    # and triggers only if they do not already exist.
    with engine.begin() as conn:
        # Add is_extracted column if it doesn't exist yet (safe to run multiple times)
        try:
            conn.execute(text(
                "ALTER TABLE archives ADD COLUMN is_extracted BOOLEAN DEFAULT 0"
            ))
        except Exception as e:
            # Almost always "duplicate column" — column already exists.
            # Any other error is interesting and should be visible.
            if "duplicate column" not in str(e).lower():
                logging.getLogger(__name__).warning("is_extracted ALTER failed: %s", e)

        # ------------------------------------------------------------------
        # One-time dedup + FTS rebuild.  Detect whether this has run before by
        # the presence of the unique index.  When already present, skip the
        # expensive dedup + FTS rebuild path (FTS rebuild on a large DB can
        # take >100 s and would otherwise run on every startup).
        # ------------------------------------------------------------------
        already_deduped = bool(conn.execute(text(
            "SELECT 1 FROM sqlite_master WHERE type='index' "
            "AND name='idx_articles_archive_path'"
        )).first())

        # Ensure the FTS virtual table exists (no-op if already there).
        conn.execute(text("""
            CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts USING fts5(
                title, summary, keywords,
                content='articles',
                content_rowid='id',
                tokenize='unicode61'
            )
        """))

        if not already_deduped:
            print("[Migration] Running one-time dedup + FTS rebuild …")

            # Drop FTS triggers so the bulk DELETE doesn't fire per-row FTS
            # delete commands (which fail with "SQL logic error" when the FTS
            # state has drifted out of sync from previous crashes).
            for trig in ("articles_ai", "articles_ad", "articles_au"):
                try:
                    conn.execute(text(f"DROP TRIGGER IF EXISTS {trig}"))
                except Exception as e:
                    logging.getLogger(__name__).warning(
                        "Could not drop trigger %s: %s", trig, e
                    )

            # Dedup — keep the lowest id per (archive_id, path).
            try:
                r = conn.execute(text("""
                    DELETE FROM articles
                    WHERE id NOT IN (
                        SELECT MIN(id) FROM articles GROUP BY archive_id, path
                    )
                """))
                if r.rowcount and r.rowcount > 0:
                    print(f"[Migration] Removed {r.rowcount} duplicate article rows.")
            except Exception as e:
                print(f"[Migration] Article dedup skipped: {e}")

            try:
                conn.execute(text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_articles_archive_path "
                    "ON articles(archive_id, path)"
                ))
            except Exception as e:
                print(f"[Migration] Unique index skipped: {e}")

            # Recompute indexed_count from real row counts.
            try:
                conn.execute(text("""
                    UPDATE archives
                    SET indexed_count = (
                        SELECT COUNT(*) FROM articles WHERE articles.archive_id = archives.id
                    )
                """))
            except Exception as e:
                print(f"[Migration] Recount skipped: {e}")

            # Full rebuild of the FTS index from articles.  This is slow on
            # large DBs (~ 100 s per 350 K rows) but only runs ONCE per
            # installation thanks to the `already_deduped` guard.
            try:
                conn.execute(text("INSERT INTO articles_fts(articles_fts) VALUES ('rebuild')"))
                print("[Migration] FTS index rebuilt from articles table.")
            except Exception as e:
                print(f"[Migration] FTS rebuild skipped: {e}")
        else:
            print("[Migration] Unique-index present — skipping dedup + FTS rebuild.")

        # Recreate triggers cleanly (idempotent).
        conn.execute(text("""
            CREATE TRIGGER IF NOT EXISTS articles_ai
            AFTER INSERT ON articles BEGIN
                INSERT INTO articles_fts(rowid, title, summary, keywords)
                VALUES (new.id, new.title, new.summary, new.keywords);
            END
        """))
        conn.execute(text("""
            CREATE TRIGGER IF NOT EXISTS articles_ad
            AFTER DELETE ON articles BEGIN
                INSERT INTO articles_fts(articles_fts, rowid, title, summary, keywords)
                VALUES ('delete', old.id, old.title, old.summary, old.keywords);
            END
        """))
        conn.execute(text("""
            CREATE TRIGGER IF NOT EXISTS articles_au
            AFTER UPDATE ON articles BEGIN
                INSERT INTO articles_fts(articles_fts, rowid, title, summary, keywords)
                VALUES ('delete', old.id, old.title, old.summary, old.keywords);
                INSERT INTO articles_fts(rowid, title, summary, keywords)
                VALUES (new.id, new.title, new.summary, new.keywords);
            END
        """))

    seed_categories()

    try:
        db = SessionLocal()
        job_registry.mark_interrupted_on_startup(db)
        db.close()
    except Exception as e:
        logging.getLogger(__name__).warning(
            "mark_interrupted_on_startup failed: %s", e
        )

    # Auto-scan the configured ZIM directory and queue background indexing.
    # Defer the actual queue start by a few seconds so the front-end's
    # initial requests (archives list, categories, settings) finish before
    # indexer threads start hammering the GIL.
    app_settings = settings_store.load()
    zim_path = app_settings.get("zim_scan_path", "").strip()
    if zim_path and Path(zim_path).is_dir():
        print(f"[Startup] Auto-scanning ZIM directory: {zim_path}")
        db = SessionLocal()
        try:
            scanned = ArchiveService.scan_directory(db, zim_path)

            def _delayed_start():
                import time as _t
                _t.sleep(5)   # let the UI's initial fetches complete first
                IndexerService.start_auto_index_queue(scanned)

            import threading as _th
            _th.Thread(target=_delayed_start, daemon=True, name="kiwi-deferred-index").start()
        except Exception as e:
            print(f"[Startup] Auto-scan error: {e}")
        finally:
            db.close()
    else:
        print("[Startup] No ZIM directory configured — open Settings to set one.")

    yield

    # ── Shutdown: cleanly stop background workers ─────────────────────
    # uvicorn/FastAPI invokes the code AFTER `yield` when the process is
    # asked to shut down. Indexer threads are daemons (they'd die anyway
    # when the process exits) but flipping the flag lets them finish their
    # current batch and commit partial progress to SQLite — avoids leaving
    # a half-written transaction or a stale "indexing" status.
    import logging as _logging
    _log = _logging.getLogger(__name__)
    _log.info("Shutdown requested — signaling background workers to stop.")
    IndexerService.request_shutdown()


app = FastAPI(
    title=APP_NAME,
    version=VERSION,
    description="Backend services for the local Offline Knowledge Intelligence System.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

# Sliding-window rate limiter — protects against runaway API loops.
# Keyed by client IP; window is 60 seconds. SSE streams are long-lived
# connections (single request) so they are not penalised by this limit.
_rate_buckets: dict = defaultdict(list)

@app.middleware("http")
async def rate_limit(request: Request, call_next):
    ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    window = _rate_buckets[ip] = [t for t in _rate_buckets[ip] if now - t < 60.0]
    if len(window) >= RATE_LIMIT_PER_MINUTE:
        return JSONResponse({"detail": "Too many requests. Slow down."}, status_code=429)
    _rate_buckets[ip].append(now)
    return await call_next(request)

app.include_router(archives.router, prefix="/api")
app.include_router(search.router, prefix="/api")
app.include_router(articles.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(health.router, prefix="/api")
app.include_router(settings_api.router, prefix="/api")


@app.get("/")
def read_root():
    return {
        "app": APP_NAME,
        "version": VERSION,
        "status": "online"
    }


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
