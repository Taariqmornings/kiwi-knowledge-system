import asyncio
import json
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Dict, Optional

from app.core.database import get_db, SessionLocal
from app.database_models import Archive, archive_categories, Category
from app.models.schemas import ArchiveSchema, ScanDirectoryRequest, AddFilesRequest, IndexStatus
from app.services.archive_service import ArchiveService
from app.services.indexer_service import IndexerService
from app.services.extractor_service import ExtractorService

router = APIRouter(prefix="/archives", tags=["archives"])

@router.get("", response_model=List[ArchiveSchema])
def list_archives(db: Session = Depends(get_db)):
    """List all imported archives and their metadata."""
    return db.query(Archive).all()

@router.post("/add-files", response_model=List[ArchiveSchema])
def add_files(req: AddFilesRequest, db: Session = Depends(get_db)):
    """Register individual ZIM files by absolute path and auto-categorize them."""
    if not req.files:
        raise HTTPException(status_code=400, detail="No files provided.")
    return ArchiveService.add_files(db, req.files)

@router.post("/scan", response_model=List[ArchiveSchema])
def scan_archives(req: ScanDirectoryRequest, db: Session = Depends(get_db)):
    """Scan a folder for ZIM files and import metadata as idle entries."""
    if not req.directory or not req.directory.strip():
        raise HTTPException(status_code=400, detail="A directory path is required.")
    archives = ArchiveService.scan_directory(db, req.directory.strip())
    return archives

@router.post("/{archive_id}/index/start")
def start_indexing(archive_id: str, db: Session = Depends(get_db)):
    """Start or resume background indexing for a ZIM archive."""
    try:
        IndexerService.resume_indexing(db, archive_id)
        return {"message": "Indexing started/resumed successfully."}
    except FileNotFoundError as fnf:
        raise HTTPException(status_code=404, detail=str(fnf))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start indexing: {e}")

@router.post("/{archive_id}/index/pause")
def pause_indexing(archive_id: str, db: Session = Depends(get_db)):
    """Pause an active indexing task."""
    IndexerService.pause_indexing(db, archive_id)
    return {"message": "Indexing paused."}

@router.post("/{archive_id}/index/cancel")
def cancel_indexing(archive_id: str, db: Session = Depends(get_db)):
    """Cancel indexing and delete partially indexed articles."""
    IndexerService.cancel_indexing(db, archive_id)
    return {"message": "Indexing cancelled and cleanup complete."}

@router.get("/{archive_id}/index/stream")
async def stream_index_progress(archive_id: str):
    """
    Server-Sent Events stream for real-time indexing progress.
    Emits one JSON object per tick until the job reaches a terminal state.
    The client should open this with EventSource and close it on terminal status.
    """
    async def generate():
        terminal = {"indexed", "failed", "cancelled"}
        while True:
            db = SessionLocal()
            try:
                archive = db.query(Archive).filter(Archive.id == archive_id).first()
                if not archive:
                    break
                payload = json.dumps({
                    "status": archive.status,
                    "progress": archive.indexed_count,
                    "total": archive.article_count,
                })
                yield f"data: {payload}\n\n"
                if archive.status in terminal:
                    break
            except Exception:
                break
            finally:
                db.close()
            await asyncio.sleep(0.75)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

@router.get("/{archive_id}/index/status", response_model=IndexStatus)
def get_indexing_status(archive_id: str, db: Session = Depends(get_db)):
    """Get indexing progress and status from memory or DB."""
    status = IndexerService.get_status(archive_id)
    if status:
        return status
    
    # Fallback to database values if not in active memory
    archive = db.query(Archive).filter(Archive.id == archive_id).first()
    if not archive:
        raise HTTPException(status_code=404, detail="Archive not found.")
        
    return {
        "status": archive.status,
        "progress": archive.indexed_count,
        "total": archive.article_count
    }

@router.delete("/{archive_id}")
def delete_archive(archive_id: str, db: Session = Depends(get_db)):
    """Delete a registered ZIM file record and its associated search index entries."""
    archive = db.query(Archive).filter(Archive.id == archive_id).first()
    if not archive:
        raise HTTPException(status_code=404, detail="Archive not found.")

    # Stop any active indexing job
    IndexerService.cancel_indexing(db, archive_id)
    # Remove extracted content from disk
    ExtractorService.delete_extraction(archive_id)

    db.delete(archive)
    db.commit()
    return {"message": f"Archive {archive_id} deleted successfully."}


@router.post("/{archive_id}/extract")
def start_extraction(archive_id: str, db: Session = Depends(get_db)):
    """
    Trigger background extraction of all article HTML from a ZIM file into
    the internal on-disk content store.  The archive must be in 'indexed'
    status.  Once extraction completes the archive transitions to 'ready',
    meaning the ZIM file is no longer required for article serving.
    """
    archive = db.query(Archive).filter(Archive.id == archive_id).first()
    if not archive:
        raise HTTPException(status_code=404, detail="Archive not found.")
    if archive.status not in ("indexed", "ready"):
        raise HTTPException(
            status_code=400,
            detail=f"Archive must be indexed before extraction (current: {archive.status}).",
        )

    started = ExtractorService.start_extraction(db, archive_id)
    if not started:
        return {"message": "Extraction already in progress."}
    return {"message": "Extraction started in background."}


@router.get("/{archive_id}/extract/status")
def extraction_status(archive_id: str, db: Session = Depends(get_db)):
    """Return extraction progress metadata for an archive."""
    archive = db.query(Archive).filter(Archive.id == archive_id).first()
    if not archive:
        raise HTTPException(status_code=404, detail="Archive not found.")
    return ExtractorService.extraction_status(archive_id)


@router.post("/cleanup-stubs")
def cleanup_stubs(db: Session = Depends(get_db)):
    """
    Delete article rows whose summary is too short to be useful — typically
    SPA meta-refresh shells or empty stubs that pollute search.  Runs in
    batches with the FTS triggers active so the index stays in sync.
    Recomputes indexed_count for affected archives.
    """
    from sqlalchemy import text as _t
    before = db.execute(_t("SELECT COUNT(*) FROM articles")).scalar() or 0
    # Capture affected archives first so we can recount only them after
    affected = [
        row[0] for row in db.execute(_t(
            "SELECT DISTINCT archive_id FROM articles "
            "WHERE LENGTH(COALESCE(summary, '')) < 40"
        )).all()
    ]
    deleted_total = 0
    while True:
        ids = [
            row[0] for row in db.execute(_t(
                "SELECT id FROM articles WHERE LENGTH(COALESCE(summary, '')) < 40 LIMIT 5000"
            )).all()
        ]
        if not ids:
            break
        db.execute(_t("DELETE FROM articles WHERE id IN :ids").bindparams(
            __import__("sqlalchemy").bindparam("ids", expanding=True)
        ), {"ids": ids})
        db.commit()
        deleted_total += len(ids)
    # Recompute affected archives' counters
    for aid in affected:
        actual = db.execute(_t("SELECT COUNT(*) FROM articles WHERE archive_id = :a"),
                            {"a": aid}).scalar() or 0
        arc = db.query(Archive).filter(Archive.id == aid).first()
        if arc:
            arc.indexed_count = actual
    db.commit()
    after = db.execute(_t("SELECT COUNT(*) FROM articles")).scalar() or 0
    return {"deleted": deleted_total, "before": before, "after": after, "archives_touched": len(affected)}

@router.post("/{archive_id}/categories")
def update_archive_categories(archive_id: str, category_ids: List[int], db: Session = Depends(get_db)):
    """Associate an archive with multiple educational categories."""
    archive = db.query(Archive).filter(Archive.id == archive_id).first()
    if not archive:
        raise HTTPException(status_code=404, detail="Archive not found.")

    # Delete existing category linkages
    db.execute(
        archive_categories.delete().where(archive_categories.c.archive_id == archive_id)
    )

    # Insert new connections
    for cat_id in category_ids:
        db.execute(
            archive_categories.insert().values(archive_id=archive_id, category_id=cat_id)
        )
    
    db.commit()
    db.refresh(archive)
    return {"message": "Categories updated successfully."}
