import logging
import re
import os
import time
import threading
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from libzim.reader import Archive as ZimArchive

logger = logging.getLogger(__name__)

from app.core.database import SessionLocal
from app.database_models import Archive, Article
from app.core.config import INDEX_BATCH_SIZE
from app.services import job_registry

TAG_RE = re.compile(r'<[^>]+>')
# Headers + inline emphasis + definition terms + code identifiers.
# Capturing these gives FTS a stronger signal for technical articles where
# the meaningful vocabulary lives in <code> blocks, <dt> tags, and
# inline <strong>/<em>, not just in H1-H3.
TERM_RE = re.compile(
    r'<(?:h[1-3]|dt|strong|em|code)[^>]*>(.*?)</(?:h[1-3]|dt|strong|em|code)>',
    re.DOTALL | re.IGNORECASE,
)
# Tags whose content we drop entirely before searching for the lead sentence
# — they tend to be navigation, scripts, or boilerplate that pollutes the
# first 500 chars of the rendered text.
_DROP_TAGS_RE = re.compile(
    r'<(script|style|nav|header|footer|aside|noscript)[^>]*>.*?</\1>',
    re.DOTALL | re.IGNORECASE,
)
# A "good" lead sentence: starts with a capital letter, ends with sentence
# punctuation, at least 40 chars long. Used to find the real article opening
# past navigation boilerplate.
_LEAD_SENTENCE_RE = re.compile(r'[A-Z][^<>]{40,}?[\.!?]\s')
# Detect SPA-style meta-refresh shells (<meta http-equiv="refresh" ...>)
# These are tiny HTML pages whose only job is to bounce the browser to a
# JS-driven index.html — they have no readable content of their own.
META_REFRESH_RE = re.compile(
    rb'<meta[^>]+http-equiv\s*=\s*["\']?refresh["\']?',
    re.IGNORECASE,
)
# Plain-text length threshold below which we consider an article "empty"
MIN_USEFUL_TEXT_LEN = 60


class IndexerService:

    @classmethod
    def get_status(cls, archive_id: str) -> Optional[dict]:
        db = SessionLocal()
        try:
            status = job_registry.get_status(db, archive_id)
            if status:
                job = job_registry.get_latest_job(db, archive_id)
                return {
                    "status": status["status"],
                    "progress": job.progress if job else 0,
                    "total": job.total if job else 0,
                }
            return None
        finally:
            db.close()

    @classmethod
    def get_all_statuses(cls) -> dict:
        db = SessionLocal()
        try:
            archives = db.query(Archive).all()
            result = {}
            for arch in archives:
                status = job_registry.get_status(db, arch.id)
                if status:
                    job = job_registry.get_latest_job(db, arch.id)
                    result[arch.id] = {
                        "status": status["status"],
                        "progress": job.progress if job else 0,
                        "total": job.total if job else 0,
                    }
                else:
                    result[arch.id] = {
                        "status": arch.status,
                        "progress": arch.indexed_count,
                        "total": arch.article_count,
                    }
            return result
        finally:
            db.close()

    @classmethod
    def pause_indexing(cls, db: Session, archive_id: str):
        job_registry.pause_job(db, archive_id)
        archive = db.query(Archive).filter(Archive.id == archive_id).first()
        if archive:
            archive.status = "paused"
            db.commit()

    @classmethod
    def resume_indexing(cls, db: Session, archive_id: str):
        archive = db.query(Archive).filter(Archive.id == archive_id).first()
        if not archive:
            raise FileNotFoundError("Archive not found in database.")

        # Paused worker threads exit immediately on pause; they cannot be signalled
        # to resume. Retire any paused/failed job so start_job can create a fresh
        # thread. The worker reads archive.indexed_count to continue from where
        # processing stopped.
        latest = job_registry.get_latest_job(db, archive_id)
        if latest and latest.status in ("paused", "failed"):
            job_registry.update_job_status(
                db, latest.id, "cancelled", error_message="Superseded by resume."
            )

        job_id = job_registry.start_job(archive_id, _index_worker, db_session=db)
        if job_id is None:
            return  # Thread already running for this archive

        archive.status = "indexing"
        db.commit()

    @classmethod
    def cancel_indexing(cls, db: Session, archive_id: str):
        job_registry.cancel_job(db, archive_id)
        archive = db.query(Archive).filter(Archive.id == archive_id).first()
        if archive:
            archive.status = "idle"
            archive.indexed_count = 0
            db.commit()

            # articles_ad trigger fires for each deleted row and removes the
            # corresponding FTS entry automatically.
            db.query(Article).filter(Article.archive_id == archive_id).delete()
            db.commit()

    # Max concurrent indexer threads. Lowered from 3 → 2 because Python's GIL
    # means each thread is fully CPU-bound during HTML parsing — three of them
    # leave no CPU for the HTTP request handlers, causing 8-second response
    # times on simple endpoints like /api/archives. Two threads keeps progress
    # decent while leaving the API responsive.
    MAX_CONCURRENT_INDEXERS = 2

    # Sleep this many ms between every batch commit so the GIL releases and
    # FastAPI request handlers can run. Tiny — doesn't slow indexing
    # measurably, but transforms responsiveness for the UI.
    INDEXER_YIELD_MS = 50

    # ── Shutdown flag ─────────────────────────────────────────────────
    # Set to True by main.py on application shutdown. Worker threads check
    # this at every batch boundary and exit cleanly so there's no half-done
    # write left in flight when the backend process is asked to stop.
    _shutdown = False

    @classmethod
    def request_shutdown(cls):
        cls._shutdown = True

    @classmethod
    def is_shutting_down(cls) -> bool:
        return cls._shutdown

    @classmethod
    def start_auto_index_queue(cls, archives: List[Archive]):
        """
        Bounded-concurrency background indexing queue.
        Up to MAX_CONCURRENT_INDEXERS archives run at once; the rest queue.
        Sorted by size ascending so small files become searchable quickly.
        Only processes archives with status 'idle'.
        """
        to_index = sorted(
            [a for a in archives if a.status == "idle" and os.path.exists(a.path)],
            key=lambda a: a.size_bytes,
        )
        if not to_index:
            return

        logger.info(
            "Queued %s archive(s) (max %s concurrent).",
            len(to_index), cls.MAX_CONCURRENT_INDEXERS,
        )

        slots = threading.Semaphore(cls.MAX_CONCURRENT_INDEXERS)

        def _drive_one(archive: Archive):
            slots.acquire()
            try:
                db = SessionLocal()
                try:
                    fresh = db.query(Archive).filter(Archive.id == archive.id).first()
                    if not fresh or fresh.status != "idle":
                        return
                    logger.info(
                        "Starting: %s (%s MB)",
                        archive.name, archive.size_bytes // (1024 * 1024),
                    )
                    cls.resume_indexing(db, archive.id)
                except Exception as e:
                    logger.warning("Could not start %s: %s", archive.name, e)
                    return
                finally:
                    db.close()

                # Wait for this archive to reach a terminal state
                while True:
                    time.sleep(5)
                    db2 = SessionLocal()
                    try:
                        a = db2.query(Archive).filter(Archive.id == archive.id).first()
                        if not a or a.status in (
                            "indexed", "failed", "cancelled", "paused"
                        ):
                            break
                    except Exception:
                        break
                    finally:
                        db2.close()
            finally:
                slots.release()

        def _queue_worker():
            workers = []
            for archive in to_index:
                t = threading.Thread(
                    target=_drive_one,
                    args=(archive,),
                    daemon=True,
                    name=f"auto-index-{archive.name[:20]}",
                )
                t.start()
                workers.append(t)
            # Don't join — daemon threads die with the process. Returning
            # immediately allows FastAPI startup to finish.

        thread = threading.Thread(
            target=_queue_worker, daemon=True, name="auto-index-queue"
        )
        thread.start()

    @staticmethod
    def extract_summary_fast(html_content: bytes) -> str:
        """
        Pull a meaningful summary out of an article. Strips navigation/script
        boilerplate first, then tries to find the first real sentence and
        captures ~500 chars from there. Falls back to plain first-500 if no
        sentence detected. Result is what powers FTS summaries AND the
        snippets shown to the LLM during RAG.
        """
        try:
            text_str = html_content.decode("utf-8", errors="ignore")
            # Strip chrome that often pollutes the first 500 chars
            text_str = _DROP_TAGS_RE.sub("", text_str)
            plain = TAG_RE.sub(" ", text_str)
            plain = " ".join(plain.split())
            if not plain:
                return ""
            # Try to skip leading navigation by jumping to the first real
            # sentence — characteristic of article body prose.
            match = _LEAD_SENTENCE_RE.search(plain[:1500])
            start = match.start() if match else 0
            return plain[start : start + 500].strip()
        except Exception:
            return ""

    @staticmethod
    def extract_keywords_fast(html_content: bytes) -> str:
        """
        Pull a deduped, space-joined list of high-signal terms out of an
        article. Looks at headers (H1-H3) plus inline emphasis (strong, em),
        definition terms (dt), and code identifiers (code) — those are where
        the real vocabulary lives in technical documentation and API
        references. FTS5 BM25 over these terms is much more discriminating
        than over the raw summary text.
        """
        try:
            text_str = html_content.decode("utf-8", errors="ignore")
            matches = TERM_RE.findall(text_str)
            seen: set = set()
            deduped: list = []
            for raw in matches:
                clean = TAG_RE.sub(" ", raw).strip()
                # Keep short identifiers (e.g. "def", "fn") but drop empties
                if not clean or len(clean) > 60:
                    continue
                if clean.lower() in seen:
                    continue
                seen.add(clean.lower())
                deduped.append(clean)
                if len(deduped) >= 25:
                    break
            return " | ".join(deduped)
        except Exception:
            return ""

    @staticmethod
    def _write_batch(db: Session, batch: List[dict]) -> int:
        """
        Bulk-insert a batch of article dicts using INSERT OR IGNORE so that
        duplicates (same archive_id+path) are skipped silently instead of
        poisoning the whole transaction. Returns the number of *successful*
        new inserts so the caller can advance its counter accurately.
        Recovers from per-batch failures by rolling back this batch only.
        """
        if not batch:
            return 0
        try:
            stmt = sqlite_insert(Article.__table__).values(batch).prefix_with("OR IGNORE")
            result = db.execute(stmt)
            # rowcount reflects rows actually inserted (ignored ones don't count)
            inserted = result.rowcount if result.rowcount is not None else len(batch)
            db.flush()
            return max(0, inserted)
        except Exception as exc:
            logger.warning("[Indexer] Batch write failed, recovering: %s", exc)
            try:
                db.rollback()
            except Exception as rb_err:
                logger.warning("[Indexer] Rollback after batch failure also failed: %s", rb_err)
            # Retry one-by-one to skip the poisoned row(s)
            saved = 0
            for row in batch:
                try:
                    stmt = sqlite_insert(Article.__table__).values([row]).prefix_with("OR IGNORE")
                    res = db.execute(stmt)
                    if res.rowcount and res.rowcount > 0:
                        saved += 1
                    db.flush()
                except Exception as row_err:
                    logger.debug("[Indexer] Single-row insert skipped: %s", row_err)
                    try:
                        db.rollback()
                    except Exception:
                        pass  # rollback failure here is benign
                    continue
            return saved


def _index_worker(archive_id: str, job_id: int):
    """Worker thread logic to batch-parse and write ZIM content to SQLite."""
    db = SessionLocal()
    try:
        archive = db.query(Archive).filter(Archive.id == archive_id).first()
        if not archive:
            job_registry.update_job_status(db, job_id, "failed", error_message="Archive not found.")
            return

        # IMPORTANT: indexed_count tracks ARTICLES indexed, not ZIM entry index.
        # Using it as a starting `idx` was a long-standing bug that caused us
        # to skip entries beyond the article count. Instead, always scan from
        # idx=0 and use a pre-loaded set of existing paths to skip already-
        # indexed articles fast. INSERT OR IGNORE provides a second safety net.
        from sqlalchemy import text as _text
        existing_paths = set(
            row[0] for row in db.execute(
                _text("SELECT path FROM articles WHERE archive_id = :a"),
                {"a": archive_id}
            )
        )

        zim = ZimArchive(archive.path)
        total_entries = zim.all_entry_count
        articles_indexed = len(existing_paths)
        job_registry.update_job_status(
            db, job_id, "indexing", progress=articles_indexed, error_message=""
        )

        # New-namespace ZIMs (libzim 3+) don't use the A/ path prefix.
        new_ns = getattr(zim, "has_new_namespace_scheme", False)

        batch_articles = []
        idx = 0

        while idx < total_entries:
            # Honor app-wide shutdown — save partial progress and exit cleanly
            if IndexerService.is_shutting_down():
                archive.indexed_count = articles_indexed
                archive.status = "paused"
                db.commit()
                return
            job = job_registry.get_job(db, job_id)
            if job is None:
                return
            if job.status == "cancelled":
                archive.indexed_count = articles_indexed
                archive.status = "idle"
                db.commit()
                return
            if job.status == "paused":
                archive.indexed_count = articles_indexed
                archive.status = "paused"
                db.commit()
                return

            try:
                entry = zim._get_entry_by_id(idx)

                # is_redirect is a property (bool), NOT a callable — no parentheses
                if entry.is_redirect:
                    idx += 1
                    continue

                path = entry.path

                # Skip already-indexed paths instantly without touching the ZIM
                # content stream. Crucial for fast resume after interruption.
                if path in existing_paths:
                    idx += 1
                    continue

                # For old-namespace ZIMs, skip non-article namespaces quickly
                # without fetching content (articles live under A/).
                if not new_ns:
                    is_article_ns = path.startswith("A/") or path.endswith((".html", ".htm"))
                    if not is_article_ns:
                        idx += 1
                        continue

                item = entry.get_item()
                mimetype = item.mimetype

                if mimetype.startswith("text/html") or mimetype.startswith("application/xhtml+xml"):
                    content_bytes = bytes(item.content)

                    # ── Skip SPA/redirect stubs ───────────────────────────
                    # Pages that are just `<meta http-equiv="refresh">` or
                    # essentially empty HTML shells aren't worth indexing —
                    # they only confuse the reader because their "content"
                    # is loaded by JS that can't run inside our iframe.
                    if META_REFRESH_RE.search(content_bytes):
                        idx += 1
                        continue
                    summary = IndexerService.extract_summary_fast(content_bytes)
                    if len(summary) < MIN_USEFUL_TEXT_LEN:
                        # Truly empty article (e.g. <body></body>) — skip
                        idx += 1
                        continue
                    keywords = IndexerService.extract_keywords_fast(content_bytes)

                    batch_articles.append({
                        "archive_id": archive_id,
                        "title": entry.title or path.split("/")[-1],
                        "path": path,
                        "summary": summary,
                        "keywords": keywords,
                        "mimetype": mimetype,
                    })
                    existing_paths.add(path)  # avoid re-processing within this run

                if len(batch_articles) >= INDEX_BATCH_SIZE:
                    inserted = IndexerService._write_batch(db, batch_articles)
                    articles_indexed += inserted
                    batch_articles.clear()
                    archive.indexed_count = articles_indexed
                    db.commit()
                    job_registry.update_job_status(db, job_id, "indexing", progress=articles_indexed)
                    # Yield the GIL so HTTP requests can be served between batches
                    time.sleep(IndexerService.INDEXER_YIELD_MS / 1000.0)

            except Exception as entry_err:
                logger.warning("Skipping entry %s in %s: %s", idx, archive.name, entry_err)
                # Make sure session isn't left in a poisoned state
                try: db.rollback()
                except Exception: pass

            idx += 1

        if batch_articles:
            inserted = IndexerService._write_batch(db, batch_articles)
            articles_indexed += inserted
            batch_articles.clear()

        # Truth-up the counter from real DB rows so the UI always shows the
        # actual indexed count even if previous runs were interrupted.
        actual = db.query(Article).filter(Article.archive_id == archive_id).count()
        archive.indexed_count = actual
        archive.status = "indexed"
        db.commit()
        job_registry.update_job_status(db, job_id, "completed", progress=actual)

    except Exception as e:
        logger.warning("Indexing error on archive %s: %s", archive_id, e)
        db.rollback()
        job_registry.update_job_status(db, job_id, "failed", error_message=str(e))
        try:
            archive = db.query(Archive).filter(Archive.id == archive_id).first()
            if archive:
                archive.status = "failed"
                db.commit()
        except Exception:
            pass
    finally:
        db.close()
