from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from typing import List, Optional

from app.core.database import get_db
from app.database_models import Category
from app.models.schemas import SearchResponse, AutocompleteResponse, CategorySchema
from app.services.search_service import SearchService

router = APIRouter(prefix="/search", tags=["search"])

@router.get("/query", response_model=SearchResponse)
def search_query(
    q: str = Query(..., min_length=1),
    archive_id: Optional[str] = Query(None),
    category_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Results per page"),
    db: Session = Depends(get_db),
):
    """
    Search articles using BM25 ranking with field boosting and typo-tolerant fallback.

    Features:
    - Quoted phrases: "machine learning" matches the exact phrase
    - Field boosting: title weighted 5x, keywords 3x, summary 1x
    - Typo-tolerant fallback via character-interleaved matching
    - Result highlighting via FTS5 mark tags
    - Full pagination metadata
    """
    result = SearchService.search(
        db,
        query_str=q,
        archive_id=archive_id,
        category_id=category_id,
        page=page,
        page_size=page_size,
    )
    return result

@router.get("/autocomplete", response_model=AutocompleteResponse)
def search_autocomplete(
    q: str = Query(..., min_length=1),
    limit: int = Query(8, ge=1, le=20),
    db: Session = Depends(get_db),
):
    """Fast prefix-based auto-suggestions for the UI search bar."""
    suggestions = SearchService.autocomplete(db, q, limit)
    return {"suggestions": suggestions}

@router.get("/categories", response_model=List[CategorySchema])
def get_categories(db: Session = Depends(get_db)):
    """List all categories available for tagging and filtering archives."""
    return db.query(Category).all()


@router.get("/random")
def random_article(
    archive_id: Optional[str] = Query(None),
    category_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Return one random article — optionally filtered by archive or category.
    Used for "Surprise me" / discovery on the home screen.
    """
    where = ""
    params: dict = {}
    joins = "JOIN archives arc ON a.archive_id = arc.id"
    if archive_id:
        where = "WHERE a.archive_id = :archive_id"
        params["archive_id"] = archive_id
    elif category_id:
        joins += " JOIN archive_categories ac ON a.archive_id = ac.archive_id"
        where = "WHERE ac.category_id = :category_id"
        params["category_id"] = category_id

    row = db.execute(text(f"""
        SELECT a.id, a.archive_id, arc.title AS archive_title,
               a.title, a.path, a.summary, a.mimetype
        FROM articles a {joins}
        {where}
        ORDER BY RANDOM()
        LIMIT 1
    """), params).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="No articles available yet.")

    return {
        "id": row.id,
        "archive_id": row.archive_id,
        "archive_title": row.archive_title,
        "title": row.title,
        "path": row.path,
        "summary": row.summary,
        "mimetype": row.mimetype,
    }

@router.get("/all", response_model=SearchResponse)
def browse_all_articles(
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    List all indexed articles across every archive, ordered alphabetically.
    No category filter — always returns content regardless of auto-categorization.
    """
    total = db.execute(text("SELECT count(*) FROM articles")).scalar() or 0
    offset = (page - 1) * page_size
    total_pages = max(1, (total + page_size - 1) // page_size)

    rows = db.execute(text("""
        SELECT a.id, a.archive_id, arc.title AS archive_title,
               a.title, a.path, a.summary, a.keywords, a.mimetype
        FROM articles a
        JOIN archives arc ON a.archive_id = arc.id
        ORDER BY arc.title, a.title
        LIMIT :limit OFFSET :offset
    """), {"limit": page_size, "offset": offset}).fetchall()

    return {
        "results": [
            {
                "id": r.id, "archive_id": r.archive_id, "archive_title": r.archive_title,
                "title": r.title, "path": r.path, "summary": r.summary,
                "keywords": r.keywords, "mimetype": r.mimetype, "score": None,
            }
            for r in rows
        ],
        "total_count": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_previous": page > 1,
    }

@router.get("/categories/{category_id}/articles", response_model=SearchResponse)
def browse_category(
    category_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    List all indexed articles belonging to a category, ordered alphabetically.
    If no articles match the category, falls back to showing all indexed articles.
    """
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found.")

    offset = (page - 1) * page_size
    params = {"category_id": category_id, "limit": page_size, "offset": offset}

    rows = db.execute(text("""
        SELECT a.id, a.archive_id, arc.title AS archive_title,
               a.title, a.path, a.summary, a.keywords, a.mimetype
        FROM articles a
        JOIN archives arc ON a.archive_id = arc.id
        JOIN archive_categories ac ON a.archive_id = ac.archive_id
        WHERE ac.category_id = :category_id
        ORDER BY arc.title, a.title
        LIMIT :limit OFFSET :offset
    """), params).fetchall()

    total = db.execute(text("""
        SELECT count(*) FROM articles a
        JOIN archive_categories ac ON a.archive_id = ac.archive_id
        WHERE ac.category_id = :category_id
    """), {"category_id": category_id}).scalar() or 0

    # Fallback: if category returns no results, show all indexed articles
    if total == 0:
        offset = (page - 1) * page_size
        total = db.execute(text("SELECT count(*) FROM articles")).scalar() or 0
        rows = db.execute(text("""
            SELECT a.id, a.archive_id, arc.title AS archive_title,
                   a.title, a.path, a.summary, a.keywords, a.mimetype
            FROM articles a
            JOIN archives arc ON a.archive_id = arc.id
            ORDER BY arc.title, a.title
            LIMIT :limit OFFSET :offset
        """), {"limit": page_size, "offset": offset}).fetchall()

    total_pages = max(1, (total + page_size - 1) // page_size)

    return {
        "results": [
            {
                "id": r.id, "archive_id": r.archive_id, "archive_title": r.archive_title,
                "title": r.title, "path": r.path, "summary": r.summary,
                "keywords": r.keywords, "mimetype": r.mimetype, "score": None,
            }
            for r in rows
        ],
        "total_count": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_previous": page > 1,
    }
