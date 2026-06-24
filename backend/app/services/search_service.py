import re
import html as _html
from typing import List, Dict, Any, Optional
from sqlalchemy import text
from sqlalchemy.orm import Session


def _safe_highlight(text: str) -> str:
    """HTML-escape FTS5 highlight output, preserving only the <mark> tags we injected.

    FTS5 highlight() operates on raw article title/summary text which may itself
    contain HTML characters. Escaping everything except our own <mark> tags prevents
    stored XSS from malicious article titles.
    """
    if not text:
        return text
    parts = re.split(r'(<mark>|</mark>)', text)
    return "".join(
        part if part in ("<mark>", "</mark>") else _html.escape(part)
        for part in parts
    )


class SearchService:
    # BM25 column weights: title=5.0, summary=1.0, keywords=3.0
    BM25_WEIGHTS = (5.0, 1.0, 3.0)

    @staticmethod
    def clean_fts_query(user_query: str) -> str:
        """
        Parse user query into FTS5 MATCH expression.

        - Quoted phrases: "machine learning" -> exact phrase match
        - Simple words: react native -> prefix match each word, AND'd
        - Escapes FTS5 special characters
        - Words under 2 chars are dropped
        """
        query = user_query.strip()
        if not query:
            return ""

        # Extract quoted phrases
        phrases = re.findall(r'"([^"]*)"', query)
        for p in phrases:
            query = query.replace(f'"{p}"', '', 1)

        # Extract remaining words, sanitize
        raw_words = re.findall(r'[^\s"()*]+', query)
        words = []
        for w in raw_words:
            w = re.sub(r'[^\w\-.]', '', w)
            if w and len(w) >= 2:
                words.append(w)

        parts = []
        if phrases:
            parts.extend(f'"{p}"' for p in phrases if p.strip())

        if words:
            for w in words:
                parts.append(f'"{w}"*')

        if not parts:
            return ""

        return " AND ".join(parts)

    @staticmethod
    def extract_terms(user_query: str) -> List[str]:
        """Extract individual search terms for fallback matching."""
        return [w for w in re.findall(r'\b\w+\b', user_query) if len(w) >= 2]

    @classmethod
    def search(
        cls,
        db: Session,
        query_str: str,
        archive_id: Optional[str] = None,
        category_id: Optional[int] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """
        Search indexed articles using BM25 ranking with field boosting.
        Returns results with highlighted snippets and pagination metadata.
        """
        fts_query = cls.clean_fts_query(query_str)
        if not fts_query:
            return cls._empty_result(page, page_size)

        offset = (page - 1) * page_size
        w0, w1, w2 = cls.BM25_WEIGHTS

        base_cols = """
            a.id, a.archive_id, a.title, a.path, a.summary, a.keywords, a.mimetype,
            arc.title as archive_title
        """
        rank_expr = f"bm25(articles_fts, {w0}, {w1}, {w2})"

        sql_query = f"""
            SELECT {base_cols},
                   {rank_expr} as score,
                   highlight(articles_fts, 0, '<mark>', '</mark>') as title_highlight,
                   snippet(articles_fts, 1, '<mark>', '</mark>', '...', 40) as snippet
            FROM articles a
            JOIN articles_fts ON a.id = articles_fts.rowid
            JOIN archives arc ON a.archive_id = arc.id
        """

        joins = []
        # Filter out stub / meta-refresh articles that have no readable text
        # — they would just render as "no content" pages and pollute results.
        conditions = [
            "articles_fts MATCH :match_query",
            "LENGTH(COALESCE(a.summary, '')) >= 40",
        ]
        params: Dict[str, Any] = {
            "match_query": fts_query,
            "limit": page_size,
            "offset": offset,
        }

        if archive_id:
            conditions.append("a.archive_id = :archive_id")
            params["archive_id"] = archive_id
        if category_id:
            joins.append("JOIN archive_categories ac ON a.archive_id = ac.archive_id")
            conditions.append("ac.category_id = :category_id")
            params["category_id"] = category_id

        if joins:
            sql_query += "\n" + "\n".join(joins)

        sql_query += "\nWHERE " + " AND ".join(conditions)
        sql_query += f"\nORDER BY {rank_expr} ASC LIMIT :limit OFFSET :offset"

        result = db.execute(text(sql_query), params)

        articles = []
        for r in result:
            articles.append({
                "id": r.id,
                "archive_id": r.archive_id,
                "archive_title": r.archive_title,
                "title": r.title,
                "path": r.path,
                "summary": r.summary,
                "keywords": r.keywords,
                "mimetype": r.mimetype,
                "score": float(r.score),
                "title_highlight": _safe_highlight(r.title_highlight),
                "snippet": _safe_highlight(r.snippet),
            })

        # Fallback chain if primary FTS returns nothing
        used_fallback = not articles
        if used_fallback:
            articles = cls._fallback_chain(db, query_str, archive_id, category_id, page_size, offset)

        # For fallback results, FTS count query would return 0 (no FTS match).
        # Use result length as a conservative total so pagination is at least correct
        # for the current page; full LIKE-based counts are a future optimisation.
        if used_fallback:
            total_count = len(articles)
        else:
            total_count = cls._count_matches(db, fts_query, archive_id, category_id, len(articles), page_size, page)

        total_pages = max(1, (total_count + page_size - 1) // page_size)

        return {
            "results": articles,
            "total_count": total_count,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_previous": page > 1,
        }

    @classmethod
    def _count_matches(
        cls,
        db: Session,
        fts_query: str,
        archive_id: Optional[str] = None,
        category_id: Optional[int] = None,
        result_count: int = 0,
        page_size: int = 20,
        page: int = 1,
    ) -> int:
        """Count total matches using FTS count for pagination."""
        if result_count < page_size and page <= 1:
            return result_count

        # Always join `articles` so we can apply the same content-length filter
        # used in the search query above; otherwise pagination shows the wrong
        # total because the count includes stub/empty articles we filter out.
        base = "FROM articles a JOIN articles_fts ON a.id = articles_fts.rowid"
        conds = [
            "articles_fts MATCH :match_query",
            "LENGTH(COALESCE(a.summary, '')) >= 40",
        ]
        count_params: Dict[str, Any] = {"match_query": fts_query}
        if archive_id:
            conds.append("a.archive_id = :archive_id")
            count_params["archive_id"] = archive_id
        if category_id:
            base += " JOIN archive_categories ac ON a.archive_id = ac.archive_id"
            conds.append("ac.category_id = :category_id")
            count_params["category_id"] = category_id
        count_sql = "SELECT count(*) " + base + " WHERE " + " AND ".join(conds)

        cnt = db.execute(text(count_sql), count_params).scalar()
        return cnt or 0

    @classmethod
    def _fallback_chain(
        cls,
        db: Session,
        query_str: str,
        archive_id: Optional[str] = None,
        category_id: Optional[int] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Progressive fallback chain for typo tolerance:
        1. FTS5 without prefix (relaxed subword matching)
        2. FTS5 with OR matching (any word matches)
        3. Character-interleaved LIKE (typo-tolerant)
        4. Simple LIKE substring (catch-all)
        """
        terms = cls.extract_terms(query_str)
        if not terms:
            return []

        # Tier 1: FTS5 without prefix
        relaxed = " AND ".join(f'"{w}"' for w in terms)
        results = cls._raw_fts(db, relaxed, archive_id, category_id, limit, offset)
        if results:
            return results

        # Tier 2: FTS5 with OR matching
        or_q = " OR ".join(f'"{w}"*' for w in terms)
        results = cls._raw_fts(db, or_q, archive_id, category_id, limit, offset)
        if results:
            return results

        # Tier 3: Interleaved character LIKE for typo tolerance
        return cls._interleaved_like(db, query_str, archive_id, category_id, limit, offset)

    @classmethod
    def _raw_fts(
        cls,
        db: Session,
        fts_query: str,
        archive_id: Optional[str] = None,
        category_id: Optional[int] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Execute a raw FTS5 MATCH query returning basic results."""
        w0, w1, w2 = cls.BM25_WEIGHTS
        rank_expr = f"bm25(articles_fts, {w0}, {w1}, {w2})"

        sql = f"""
            SELECT a.id, a.archive_id, a.title, a.path, a.summary, a.keywords, a.mimetype,
                   arc.title as archive_title, {rank_expr} as score
            FROM articles a
            JOIN articles_fts ON a.id = articles_fts.rowid
            JOIN archives arc ON a.archive_id = arc.id
        """
        joins = []
        conds = ["articles_fts MATCH :match_query"]
        params = {"match_query": fts_query, "limit": limit, "offset": offset}

        if archive_id:
            conds.append("a.archive_id = :archive_id")
            params["archive_id"] = archive_id
        if category_id:
            joins.append("JOIN archive_categories ac ON a.archive_id = ac.archive_id")
            conds.append("ac.category_id = :category_id")
            params["category_id"] = category_id

        if joins:
            sql += "\n" + "\n".join(joins)

        sql += "\nWHERE " + " AND ".join(conds)
        sql += f"\nORDER BY {rank_expr} ASC LIMIT :limit OFFSET :offset"

        return [
            {
                "id": r.id,
                "archive_id": r.archive_id,
                "archive_title": r.archive_title,
                "title": r.title,
                "path": r.path,
                "summary": r.summary,
                "keywords": r.keywords,
                "mimetype": r.mimetype,
                "score": float(r.score),
            }
            for r in db.execute(text(sql), params)
        ]

    @classmethod
    def _interleaved_like(
        cls,
        db: Session,
        query_str: str,
        archive_id: Optional[str] = None,
        category_id: Optional[int] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Typo-tolerant LIKE using character-interleaved patterns.
        'react' -> '%r%e%a%c%t%' allows extra/missing characters between letters.
        """
        clean = re.sub(r'\b(the|a|an|of|in|on|at|for|to|and|or|is|are)\b', '', query_str, flags=re.IGNORECASE).strip()
        if len(clean) < 2:
            return cls._simple_like(db, query_str, archive_id, category_id, limit, offset)

        # Interleave characters, replace spaces with % for word-boundary tolerance
        pattern = '%' + '%'.join(clean) + '%'

        sql = """
            SELECT a.id, a.archive_id, a.title, a.path, a.summary, a.keywords, a.mimetype,
                   arc.title as archive_title
            FROM articles a
            JOIN archives arc ON a.archive_id = arc.id
        """
        joins = []
        conds = ["a.title LIKE :like_query"]
        params = {"like_query": pattern, "limit": limit, "offset": offset}

        if archive_id:
            conds.append("a.archive_id = :archive_id")
            params["archive_id"] = archive_id
        if category_id:
            joins.append("JOIN archive_categories ac ON a.archive_id = ac.archive_id")
            conds.append("ac.category_id = :category_id")
            params["category_id"] = category_id

        if joins:
            sql += "\n" + "\n".join(joins)

        sql += "\nWHERE " + " AND ".join(conds)
        sql += "\nLIMIT :limit OFFSET :offset"

        results = [
            {
                "id": r.id,
                "archive_id": r.archive_id,
                "archive_title": r.archive_title,
                "title": r.title,
                "path": r.path,
                "summary": r.summary,
                "keywords": r.keywords,
                "mimetype": r.mimetype,
                "score": None,
            }
            for r in db.execute(text(sql), params)
        ]

        if not results:
            return cls._simple_like(db, query_str, archive_id, category_id, limit, offset)

        return results

    @classmethod
    def _simple_like(
        cls,
        db: Session,
        query_str: str,
        archive_id: Optional[str] = None,
        category_id: Optional[int] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Simple LIKE '%query%' fallback."""
        sql = """
            SELECT a.id, a.archive_id, a.title, a.path, a.summary, a.keywords, a.mimetype,
                   arc.title as archive_title
            FROM articles a
            JOIN archives arc ON a.archive_id = arc.id
        """
        joins = []
        conds = ["a.title LIKE :like_query"]
        params = {"like_query": f"%{query_str}%", "limit": limit, "offset": offset}

        if archive_id:
            conds.append("a.archive_id = :archive_id")
            params["archive_id"] = archive_id
        if category_id:
            joins.append("JOIN archive_categories ac ON a.archive_id = ac.archive_id")
            conds.append("ac.category_id = :category_id")
            params["category_id"] = category_id

        if joins:
            sql += "\n" + "\n".join(joins)

        sql += "\nWHERE " + " AND ".join(conds)
        sql += "\nLIMIT :limit OFFSET :offset"

        return [
            {
                "id": r.id,
                "archive_id": r.archive_id,
                "archive_title": r.archive_title,
                "title": r.title,
                "path": r.path,
                "summary": r.summary,
                "keywords": r.keywords,
                "mimetype": r.mimetype,
                "score": None,
            }
            for r in db.execute(text(sql), params)
        ]

    @staticmethod
    def _empty_result(page: int, page_size: int) -> Dict[str, Any]:
        return {
            "results": [],
            "total_count": 0,
            "page": page,
            "page_size": page_size,
            "total_pages": 0,
            "has_next": False,
            "has_previous": False,
        }

    @staticmethod
    def autocomplete(db: Session, partial_query: str, limit: int = 8) -> List[Dict[str, Any]]:
        """
        Fast prefix matching against article titles using FTS5 column query.
        Returns up to 'limit' matching title suggestions.
        """
        if not partial_query.strip():
            return []

        words = re.findall(r'\b\w+\b', partial_query)
        if not words:
            return []

        fts_match = " AND ".join(f'title:"{w}"*' for w in words)

        sql = """
            SELECT DISTINCT a.title, a.path, a.archive_id, arc.title as archive_title
            FROM articles a
            JOIN articles_fts ON a.id = articles_fts.rowid
            JOIN archives arc ON a.archive_id = arc.id
            WHERE articles_fts MATCH :match_query
            LIMIT :limit
        """

        return [
            {"title": r.title, "path": r.path, "archive_id": r.archive_id, "archive_title": r.archive_title}
            for r in db.execute(text(sql), {"match_query": fts_match, "limit": limit})
        ]
