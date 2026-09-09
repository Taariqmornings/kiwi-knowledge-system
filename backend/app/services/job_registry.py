"""
Persisted job registry for background indexing tasks.

Replaces the in-memory Dict-based job tracking with a database-backed
registry that survives server restarts and provides proper lifecycle
management (create, start, pause, cancel, complete, fail).

In-memory cache is used only for quick status lookups and thread references;
the database is the source of truth.
"""
import threading
from datetime import datetime
from typing import Dict, Optional, Tuple

from sqlalchemy.orm import Session

from app.database_models import IndexJob, Archive
from app.core.database import SessionLocal

# In-memory tracking: {archive_id: {"job_id": int, "thread": Thread, "status": str}}
_job_cache: Dict[str, Dict] = {}
_cache_lock = threading.Lock()


def _get_cache(archive_id: str) -> Optional[Dict]:
    with _cache_lock:
        return _job_cache.get(archive_id)


def _set_cache(archive_id: str, data: Dict):
    with _cache_lock:
        _job_cache[archive_id] = data


def _del_cache(archive_id: str):
    with _cache_lock:
        _job_cache.pop(archive_id, None)


# --- Thread worker registry ---
# Maps archive_id -> threading.Thread for active workers
_workers: Dict[str, threading.Thread] = {}
_workers_lock = threading.Lock()


def create_job(db: Session, archive_id: str, total: int = 0) -> IndexJob:
    job = IndexJob(
        archive_id=archive_id,
        status="pending",
        progress=0,
        total=total,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def get_job(db: Session, job_id: int) -> Optional[IndexJob]:
    return db.query(IndexJob).filter(IndexJob.id == job_id).first()


def get_latest_job(db: Session, archive_id: str) -> Optional[IndexJob]:
    return (
        db.query(IndexJob)
        .filter(IndexJob.archive_id == archive_id)
        .order_by(IndexJob.id.desc())
        .first()
    )


def get_jobs_for_archive(db: Session, archive_id: str) -> list[IndexJob]:
    return (
        db.query(IndexJob)
        .filter(IndexJob.archive_id == archive_id)
        .order_by(IndexJob.id.desc())
        .all()
    )


def update_job_status(
    db: Session, job_id: int, status: str, progress: Optional[int] = None, error_message: Optional[str] = None
) -> Optional[IndexJob]:
    job = db.query(IndexJob).filter(IndexJob.id == job_id).first()
    if not job:
        return None
    now = datetime.utcnow()
    job.status = status
    job.updated_at = now
    if progress is not None:
        job.progress = progress
    if error_message is not None:
        job.error_message = error_message
    if status == "running" and job.started_at is None:
        job.started_at = now
    if status in ("completed", "failed", "cancelled") and job.completed_at is None:
        job.completed_at = now
    db.commit()
    db.refresh(job)
    return job


def get_all_active_jobs(db: Session) -> list[IndexJob]:
    # "indexing" is the live status the worker writes while it parses batches
    # (start_job first sets "running"); all four must count as active so that
    # pause/cancel/startup-cleanup always see in-flight work.
    return (
        db.query(IndexJob)
        .filter(IndexJob.status.in_(["pending", "running", "paused", "indexing"]))
        .all()
    )


def start_job(archive_id: str, worker_fn, *, db_session=None) -> Optional[int]:
    """
    Start a background thread for the given archive.
    Creates a new job in 'running' status if none is pending/running.
    Returns the job_id or None if already running.
    """
    close_db = db_session is None
    db = db_session or SessionLocal()
    try:
        latest = get_latest_job(db, archive_id)
        if latest and latest.status in ("running", "indexing"):
            return None

        job = create_job(db, archive_id)
        job_id = job.id

        update_job_status(db, job_id, "running")
        _set_cache(archive_id, {"job_id": job_id, "status": "running"})

        def _wrapped_worker():
            try:
                worker_fn(archive_id, job_id)
            finally:
                if close_db:
                    pass

        thread = threading.Thread(target=_wrapped_worker, daemon=True)
        with _workers_lock:
            _workers[archive_id] = thread
        thread.start()
        return job_id
    finally:
        if close_db:
            db.close()


def cancel_job(db: Session, archive_id: str) -> Optional[IndexJob]:
    """Mark latest job as cancelled and stop the worker."""
    job = get_latest_job(db, archive_id)
    if job and job.status in ("pending", "running", "paused", "indexing"):
        update_job_status(db, job.id, "cancelled", progress=job.progress)

    with _cache_lock:
        cached = _job_cache.get(archive_id)
        if cached:
            cached["status"] = "cancelled"

    # Thread will check status and exit on its own
    return job


def pause_job(db: Session, archive_id: str) -> Optional[IndexJob]:
    job = get_latest_job(db, archive_id)
    if job and job.status in ("running", "indexing"):
        update_job_status(db, job.id, "paused")
        with _cache_lock:
            cached = _job_cache.get(archive_id)
            if cached:
                cached["status"] = "paused"
    return job


def resume_job(db: Session, archive_id: str) -> Optional[IndexJob]:
    """Resume a paused job. If no paused job, start a new one."""
    job = get_latest_job(db, archive_id)
    if job and job.status == "paused":
        update_job_status(db, job.id, "running")
        with _cache_lock:
            cached = _job_cache.get(archive_id)
            if cached:
                cached["status"] = "running"
        return job
    return None


def get_status(db: Session, archive_id: str) -> Optional[dict]:
    """Get current status from cache or DB for an archive."""
    cached = _get_cache(archive_id)
    if cached:
        return {"status": cached["status"], "job_id": cached.get("job_id")}

    job = get_latest_job(db, archive_id)
    if job:
        return {"status": job.status, "job_id": job.id, "progress": job.progress, "total": job.total}
    return None


def mark_interrupted_on_startup(db: Session):
    """
    On application startup, mark any 'running' or 'pending' jobs as 'failed'
    since they were left in-flight from a previous server instance, and reset
    the associated archive status from a stale 'indexing' back to 'idle'.

    IMPORTANT: do NOT zero indexed_count — the articles in the database from
    the previous partial run are still valid (the UNIQUE index prevents
    duplicates on re-run).  The counter is recomputed from real row counts
    so the UI shows truth, and a fresh resume will pick up where it left off.
    """
    from sqlalchemy import text as _text
    jobs = get_all_active_jobs(db)
    affected_archives = set()
    for job in jobs:
        update_job_status(
            db, job.id, "failed",
            error_message="Server was restarted while job was in progress."
        )
        affected_archives.add(job.archive_id)

    # Also catch any archive whose status is stale 'indexing' even without a job row
    stale = db.query(Archive).filter(Archive.status.in_(("indexing", "pending"))).all()
    for a in stale:
        affected_archives.add(a.id)

    for archive_id in affected_archives:
        archive = db.query(Archive).filter(Archive.id == archive_id).first()
        if not archive:
            continue
        actual = db.execute(
            _text("SELECT COUNT(*) FROM articles WHERE archive_id = :a"),
            {"a": archive_id}
        ).scalar() or 0
        archive.indexed_count = actual
        archive.status = "indexed" if actual > 0 and actual >= archive.article_count else "idle"
    db.commit()
