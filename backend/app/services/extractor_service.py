"""
ExtractorService — Ingestion Pipeline
======================================
Extracts article HTML from ZIM files into an on-disk content store so the
system can serve articles without needing the original ZIM at runtime.

Directory layout
----------------
data/
  extracted/
    {archive_id}/
      html/
        {zim_entry_path}          ← raw HTML bytes (renamed extension → .html)
      media/
        {zim_asset_path}          ← cached binary assets (images, CSS, fonts…)
      meta.json                   ← extraction metadata (progress, article count)

Serving priority (articles.py):
  1. data/extracted/{id}/html/{path}  — fastest, ZIM not needed
  2. live read from ZIM file           — fallback while extraction is running
"""

from __future__ import annotations

import json
import logging
import re
import threading
from pathlib import Path
from typing import Optional, Tuple

from app.core.config import DATA_DIR

logger = logging.getLogger(__name__)

# Base extraction directory
_BASE = Path(DATA_DIR) / "extracted"

# Archive ids are generated from ZIM file paths (md5 hex digests), but the
# guard below only needs to guarantee the value is safe to use as a single
# path segment — no separators, no traversal, no control characters.
_ARCHIVE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def _safe_archive_id(archive_id: str) -> str:
    """Validate an archive id before it is used to build a disk path."""
    if not _ARCHIVE_ID_RE.fullmatch(archive_id or ""):
        raise ValueError("Invalid archive id")
    return archive_id


def _safe_zim_path(zim_path: str) -> str:
    """Validate and normalise a ZIM entry path before it is joined to disk.

    Rejects null bytes, absolute paths, and any ``..`` component so that a
    malicious or malformed entry path can never escape the extraction store.
    """
    if not zim_path or "\0" in zim_path:
        raise ValueError("Invalid entry path")
    # Normalise separators and strip a leading slash.
    cleaned = zim_path.replace("\\", "/").lstrip("/")
    # Decode URL-encoded sequences that could mask traversal.
    cleaned = cleaned.replace("%2e", ".").replace("%2E", ".")
    if cleaned.startswith("/") or ".." in cleaned.split("/"):
        raise ValueError("Unsafe entry path")
    return cleaned


def _html_path(archive_id: str, zim_path: str) -> Path:
    """Map a ZIM entry path to its on-disk HTML file path."""
    safe = _safe_zim_path(zim_path)
    return _BASE / _safe_archive_id(archive_id) / "html" / safe


def _media_path(archive_id: str, zim_path: str) -> Path:
    """Map a ZIM asset path to its on-disk media cache path."""
    safe = _safe_zim_path(zim_path)
    return _BASE / _safe_archive_id(archive_id) / "media" / safe


def _meta_path(archive_id: str) -> Path:
    return _BASE / _safe_archive_id(archive_id) / "meta.json"


# ---------------------------------------------------------------------------
# Extraction lock — one background thread per archive at a time
# ---------------------------------------------------------------------------
_active_extractions: dict[str, bool] = {}
_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class ExtractorService:

    # ── Read ────────────────────────────────────────────────────────────────

    @classmethod
    def get_extracted_html(cls, archive_id: str, zim_path: str) -> Optional[bytes]:
        """
        Return the extracted HTML bytes for a ZIM entry if it exists on disk,
        else return None (caller should fall back to live ZIM read).
        """
        p = _html_path(archive_id, zim_path)
        if p.exists():
            try:
                return p.read_bytes()
            except OSError:
                return None
        return None

    @classmethod
    def get_cached_media(
        cls, archive_id: str, zim_path: str
    ) -> Optional[Tuple[bytes, str]]:
        """
        Return (bytes, mimetype) for a cached media asset, or None.
        The mimetype is stored alongside the file in a tiny sidecar.
        """
        p = _media_path(archive_id, zim_path)
        sidecar = p.with_suffix(p.suffix + ".mime")
        if p.exists():
            try:
                content = p.read_bytes()
                mimetype = (
                    sidecar.read_text(encoding="utf-8").strip()
                    if sidecar.exists()
                    else "application/octet-stream"
                )
                return content, mimetype
            except OSError:
                return None
        return None

    @classmethod
    def cache_media(
        cls, archive_id: str, zim_path: str, content: bytes, mimetype: str
    ) -> None:
        """Write a media asset to the cache.  Silent on failure."""
        try:
            p = _media_path(archive_id, zim_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(content)
            p.with_suffix(p.suffix + ".mime").write_text(
                mimetype, encoding="utf-8"
            )
        except OSError:
            pass

    # ── Write (extraction) ──────────────────────────────────────────────────

    @classmethod
    def start_extraction(cls, db, archive_id: str) -> bool:
        """
        Launch background extraction for *archive_id*.
        Returns True if started, False if already running.
        """
        from app.database_models import Archive, Article
        from app.services.archive_service import ArchiveService

        with _lock:
            if _active_extractions.get(archive_id):
                return False
            _active_extractions[archive_id] = True

        def _run():
            from app.core.database import SessionLocal

            db_local = SessionLocal()
            try:
                archive = db_local.query(Archive).filter(
                    Archive.id == archive_id
                ).first()
                if not archive:
                    return

                # Mark as extracting
                archive.status = "extracting"
                db_local.commit()

                articles = (
                    db_local.query(Article)
                    .filter(Article.archive_id == archive_id)
                    .all()
                )

                total = len(articles)
                done = 0

                for article in articles:
                    try:
                        content, _mime, _title = ArchiveService.get_entry_data(
                            archive.path, article.path
                        )
                        p = _html_path(archive_id, article.path)
                        p.parent.mkdir(parents=True, exist_ok=True)
                        p.write_bytes(content)
                        done += 1
                    except Exception:
                        pass  # Skip broken entries; content will fall back to ZIM

                # Write extraction metadata
                meta_p = _meta_path(archive_id)
                meta_p.parent.mkdir(parents=True, exist_ok=True)
                meta_p.write_text(
                    json.dumps(
                        {"archive_id": archive_id, "extracted": done, "total": total}
                    ),
                    encoding="utf-8",
                )

                # Update archive status in DB
                archive_fresh = db_local.query(Archive).filter(
                    Archive.id == archive_id
                ).first()
                if archive_fresh:
                    archive_fresh.status = "ready" if done == total else "indexed"
                    archive_fresh.is_extracted = done > 0
                    db_local.commit()

            except Exception as exc:
                logger.warning("Extraction error for %s: %s", archive_id, exc)
                try:
                    arch = db_local.query(Archive).filter(
                        Archive.id == archive_id
                    ).first()
                    if arch:
                        arch.status = "indexed"
                        db_local.commit()
                except Exception:
                    pass
            finally:
                db_local.close()
                with _lock:
                    _active_extractions.pop(archive_id, None)

        t = threading.Thread(target=_run, name=f"extractor-{archive_id}", daemon=True)
        t.start()
        return True

    @classmethod
    def extraction_status(cls, archive_id: str) -> dict:
        """Return extraction metadata if available."""
        p = _meta_path(archive_id)
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"archive_id": archive_id, "extracted": 0, "total": 0}

    @classmethod
    def delete_extraction(cls, archive_id: str) -> None:
        """Remove all extracted files for an archive (e.g. on archive delete)."""
        import shutil

        target = _BASE / _safe_archive_id(archive_id)
        if target.exists():
            try:
                shutil.rmtree(target)
            except OSError:
                pass
