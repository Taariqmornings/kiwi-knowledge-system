from fastapi import APIRouter, Depends, HTTPException, Query, Response, Request
from sqlalchemy.orm import Session
import re

from app.core.config import ALLOWED_ORIGINS
from app.core.database import get_db
from app.database_models import Archive, Article
from app.services.archive_service import ArchiveService
from app.services.transformer_service import TransformerService
from app.services.extractor_service import ExtractorService

router = APIRouter(prefix="/articles", tags=["articles"])

# Strip HTML tags + collapse whitespace for the preview endpoint
_TAG_RE = re.compile(r"<[^>]+>")

# Origins the Electron iframe / file:// page is served from. The wildcard
# header is NOT used — CORS here is limited to the app's own origins so a
# third-party site can never read files off the local API.
_ORIGIN_ALLOWLIST = set(ALLOWED_ORIGINS)


def _cors_headers(request: Request) -> dict:
    """Return per-response CORS headers restricted to the app's own origins."""
    origin = request.headers.get("origin")
    if origin in _ORIGIN_ALLOWLIST:
        return {"Access-Control-Allow-Origin": origin}
    return {}


def _suggestions_for(db, archive_id: str, backend_url: str, n: int = 5):
    """Return up to n real (non-stub) articles from the same archive as suggestions."""
    if not archive_id:
        return []
    from sqlalchemy import text as _t
    rows = db.execute(_t("""
        SELECT title, path FROM articles
        WHERE archive_id = :a AND LENGTH(COALESCE(summary, '')) >= 60
        ORDER BY RANDOM() LIMIT :n
    """), {"a": archive_id, "n": n}).all()
    return [
        {"title": r[0], "href": f"{backend_url}/api/articles/{archive_id}/view/{r[1]}"}
        for r in rows
    ]


def _empty_state_response(title: str, reason: str, hint: str,
                          archive_title: str, theme: str,
                          request: Request,
                          suggestions: list | None = None) -> Response:
    """Wrap TransformerService._render_empty_state in a Response so callers
    can return a polished page from any failure path instead of a JSON 500."""
    html = TransformerService._render_empty_state(
        title=title, reason=reason, hint=hint,
        archive_title=archive_title, theme=theme,
        suggestions=suggestions,
    )
    return Response(content=html, media_type="text/html; charset=utf-8", headers=_cors_headers(request))


def _invalid_link_response(archive_title: str, theme: str, request: Request) -> Response:
    """Render a safe empty-state page for a malformed / unsafe article link."""
    return _empty_state_response(
        title="Invalid article link",
        reason="The link you followed isn't a valid article path inside this archive.",
        hint="Try one of these articles from the same archive instead, or use Search.",
        archive_title=archive_title, theme=theme,
        request=request,
    )


@router.get("/{archive_id}/view/{path:path}", response_class=Response)
def view_article(
    archive_id: str,
    path: str,
    request: Request,
    theme: str = Query("dark"),
    db: Session = Depends(get_db),
):
    """
    Always returns HTTP 200 with a rendered HTML page — either the article
    or a styled empty state explaining what went wrong. The iframe must
    never see a raw FastAPI JSON 500 or a browser network-error page.
    """
    archive = db.query(Archive).filter(Archive.id == archive_id).first()
    if not archive:
        return _empty_state_response(
            title="Archive not found",
            reason="This archive is no longer in the database (it may have been removed).",
            hint="Go to ZIM Archives to see what's registered.",
            archive_title="", theme=theme, request=request,
        )

    archive_title = archive.title or archive.name

    try:
        content = ExtractorService.get_extracted_html(archive_id, path)
        mimetype = "text/html"
        if content is None:
            content, mimetype, _title = ArchiveService.get_entry_data(archive.path, path)

        if mimetype.startswith("text/html") or mimetype.startswith("application/xhtml+xml"):
            backend_url = str(request.base_url).rstrip("/")
            modernized = TransformerService.transform_html(
                content, archive_id, path,
                theme=theme, backend_url=backend_url, archive_title=archive_title,
            )
            return Response(content=modernized, media_type="text/html; charset=utf-8", headers=_cors_headers(request))

        return Response(content=content, media_type=mimetype, headers=_cors_headers(request))

    except ValueError:
        return _invalid_link_response(archive_title, theme, request)
    except KeyError:
        backend_url = str(request.base_url).rstrip("/")
        return _empty_state_response(
            title=path.split("/")[-1] or "Article",
            reason="That entry isn't present inside the ZIM file. It may be a broken link or a stale database record.",
            hint="Try one of these articles from the same archive instead, or use Search.",
            archive_title=archive_title, theme=theme,
            request=request,
            suggestions=_suggestions_for(db, archive_id, backend_url),
        )
    except FileNotFoundError:
        # ZIM file moved/deleted — mark the archive failed so the UI surfaces it
        try:
            archive.status = "failed"
            db.commit()
        except Exception:
            db.rollback()
        return _empty_state_response(
            title=archive_title,
            reason="The original ZIM file is no longer at its registered path. The archive has been marked as failed.",
            hint="Go to Settings and re-scan the ZIM directory, or re-add the file.",
            archive_title=archive_title, theme=theme,
            request=request,
        )
    except Exception as e:
        return _empty_state_response(
            title="Couldn't load article",
            reason=f"An unexpected error occurred while reading this article: {e}",
            hint="Try another article, or report this if it keeps happening.",
            archive_title=archive_title, theme=theme,
            request=request,
        )


@router.get("/{archive_id}/preview/{path:path}")
def article_preview(
    archive_id: str,
    path: str,
    db: Session = Depends(get_db),
):
    """
    Lightweight preview for a Wikipedia-style hover card.
    Returns title + first 240 chars of the article body + archive name.
    Fast: reads from the indexed summary if available, falls back to ZIM.
    """
    archive = db.query(Archive).filter(Archive.id == archive_id).first()
    if not archive:
        raise HTTPException(status_code=404, detail="Archive not found.")

    # Prefer pre-indexed summary (microseconds vs reading ZIM)
    art = (
        db.query(Article)
        .filter(Article.archive_id == archive_id, Article.path == path)
        .first()
    )
    if art and art.summary:
        snippet = art.summary[:240]
        return {
            "title": art.title,
            "snippet": snippet + ("…" if len(art.summary) > 240 else ""),
            "archive_title": archive.title or archive.name,
            "archive_id": archive_id,
            "path": path,
        }

    # Fallback: live read from ZIM and strip
    try:
        content, _mime, _t = ArchiveService.get_entry_data(archive.path, path)
        text = _TAG_RE.sub(" ", content.decode("utf-8", errors="ignore"))
        text = " ".join(text.split())[:240]
        return {
            "title": (art.title if art else path.split("/")[-1]),
            "snippet": text + "…",
            "archive_title": archive.title or archive.name,
            "archive_id": archive_id,
            "path": path,
        }
    except Exception:
        raise HTTPException(status_code=404, detail="No preview available.")


@router.get("/{archive_id}/media/{path:path}")
def get_media_asset(
    archive_id: str,
    path: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Stream binary assets (images, video, audio, CSS, fonts) from the cached
    extraction store if available, otherwise from the ZIM file.  Results are
    cached on first access so subsequent requests skip the ZIM entirely.
    """
    archive = db.query(Archive).filter(Archive.id == archive_id).first()
    if not archive:
        raise HTTPException(status_code=404, detail="Archive not found in database.")

    try:
        # Try media cache first
        cached = ExtractorService.get_cached_media(archive_id, path)
        if cached is not None:
            content, mimetype = cached
            return Response(
                content=content,
                media_type=mimetype,
                headers={**_cors_headers(request), "Cache-Control": "public, max-age=86400"},
            )

        # Live read from ZIM, cache result
        content, mimetype, _title = ArchiveService.get_entry_data(archive.path, path)
        ExtractorService.cache_media(archive_id, path, content, mimetype)

        return Response(
            content=content,
            media_type=mimetype,
            headers={**_cors_headers(request), "Cache-Control": "public, max-age=86400"},
        )

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid asset path.")
    except KeyError:
        raise HTTPException(
            status_code=404, detail=f"Asset '{path}' not found in archive."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Media reader error: {e}")
