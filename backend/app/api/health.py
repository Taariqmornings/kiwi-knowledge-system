"""
/api/health — lightweight system status for the Settings dashboard and
external monitoring. Returns counters that are cheap to compute.
"""
import os
import time
import threading
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import DATABASE_PATH, DATA_DIR
from app.core.database import get_db
from app.services.llm_service import LlmService

router = APIRouter(prefix="/health", tags=["health"])

_START = time.time()


def _dir_size_mb(path: Path) -> float:
    """Recursive size of a directory in MiB. Returns 0 on any error / missing."""
    if not path.exists():
        return 0.0
    total = 0
    try:
        for p in path.rglob("*"):
            try:
                if p.is_file():
                    total += p.stat().st_size
            except OSError:
                pass
    except OSError:
        return 0.0
    return round(total / (1024 * 1024), 1)


@router.get("")
def health(db: Session = Depends(get_db)):
    articles = db.execute(text("SELECT COUNT(*) FROM articles")).scalar() or 0
    statuses = {s: n for s, n in
                db.execute(text("SELECT status, COUNT(*) FROM archives GROUP BY status")).all()}
    db_size = Path(DATABASE_PATH).stat().st_size if Path(DATABASE_PATH).exists() else 0
    extracted_dir = Path(DATA_DIR) / "extracted"
    return {
        "articles": articles,
        "archives_by_status": statuses,
        "db_size_mb": round(db_size / (1024 * 1024), 1),
        "extracted_cache_mb": _dir_size_mb(extracted_dir),
        "model_reachable": LlmService.is_loaded(),
        "uptime_seconds": int(time.time() - _START),
        "cpu_count": os.cpu_count(),
        # Live thread count — useful sanity check that nothing leaked
        "active_threads": threading.active_count(),
    }


@router.post("/stop-background-work")
def stop_background_work():
    """
    Best-effort: pause every active indexer thread. Threads commit their
    current batch then exit cleanly. Frees the CPU immediately. Safe to call
    any time; archives in 'indexing' status flip to 'paused' and can be
    resumed manually from the ZIM Archives panel.
    """
    from app.services.indexer_service import IndexerService
    from app.services.job_registry import get_all_active_jobs, pause_job
    from app.core.database import SessionLocal
    db = SessionLocal()
    try:
        jobs = get_all_active_jobs(db)
        paused = 0
        for j in jobs:
            try:
                pause_job(db, j.archive_id)
                paused += 1
            except Exception:
                pass
        # Also flip the global flag so any in-flight batch will exit at next check
        IndexerService.request_shutdown()
        # Clear it again immediately so subsequent restarts of indexing work
        IndexerService._shutdown = False
        return {"paused_jobs": paused}
    finally:
        db.close()
