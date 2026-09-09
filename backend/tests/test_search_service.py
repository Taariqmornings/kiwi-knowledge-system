"""Tests for the search service with seeded database."""
import pytest
from sqlalchemy import text

from app.services.search_service import SearchService
from app.database_models import Archive, Article


def _seed_article(db, archive_id, title, path, summary="", keywords=""):
    """Helper to insert an article and its FTS5 entry."""
    art = Article(
        archive_id=archive_id,
        title=title,
        path=path,
        summary=summary,
        keywords=keywords,
        mimetype="text/html",
    )
    db.add(art)
    db.flush()
    db.execute(text(
        "INSERT INTO articles_fts(rowid, title, summary, keywords) "
        "VALUES (:rowid, :title, :summary, :keywords)"
    ), {
        "rowid": art.id,
        "title": title,
        "summary": summary,
        "keywords": keywords,
    })
    return art


@pytest.fixture
def seeded_db(db_session):
    """Seed the test database with an archive and sample articles."""
    archive = Archive(
        id="test-archive-001",
        name="test.zim",
        path="/tmp/test.zim",
        title="Test Archive",
        description="A test archive",
        creator="Tester",
        date="2024-01-01",
        language="eng",
        size_bytes=1000,
        article_count=5,
        status="indexed",
        indexed_count=5,
    )
    db_session.add(archive)
    db_session.commit()

    _seed_article(db_session, "test-archive-001",
                  "Python Programming", "A/python.html",
                  "Python is a high-level, general-purpose programming language",
                  "python | programming | language")
    _seed_article(db_session, "test-archive-001",
                  "Machine Learning", "A/ml.html",
                  "Machine learning is a subset of artificial intelligence that lets computers learn from data",
                  "machine | learning | AI")
    _seed_article(db_session, "test-archive-001",
                  "React Native", "A/react.html",
                  "React Native is a JavaScript framework for building mobile applications for iOS and Android",
                  "react | native | mobile")
    _seed_article(db_session, "test-archive-001",
                  "Deep Learning Guide", "A/deep.html",
                  "Deep learning uses neural networks with many layers to model complex patterns in data",
                  "deep | learning | neural")
    db_session.commit()
    return db_session


def test_search_basic(seeded_db):
    """Basic keyword search returns matching articles."""
    results = SearchService.search(seeded_db, "python")
    assert len(results["results"]) > 0
    titles = [r["title"] for r in results["results"]]
    assert "Python Programming" in titles


def test_search_no_match(seeded_db):
    """Search with non-matching query returns empty."""
    results = SearchService.search(seeded_db, "zzzzzzzzz")
    assert results["results"] == []
    assert results["total_count"] == 0


def test_search_phrase(seeded_db):
    """Phrase search returns exact matches."""
    results = SearchService.search(seeded_db, '"Machine Learning"')
    titles = [r["title"] for r in results["results"]]
    assert "Machine Learning" in titles


def test_search_title_boosted(seeded_db):
    """Title matches rank higher due to BM25 boost."""
    results = SearchService.search(seeded_db, "learning")
    titles = [r["title"] for r in results["results"]]
    # "Machine Learning" has learning in title (boosted)
    # "Deep Learning Guide" also has learning in title
    assert "Machine Learning" in titles
    assert "Deep Learning Guide" in titles


def test_search_pagination(seeded_db):
    """Search returns paginated results with metadata."""
    results = SearchService.search(seeded_db, "learning", page=1, page_size=1)
    assert len(results["results"]) == 1
    assert results["total_count"] > 0
    assert results["page"] == 1
    assert results["page_size"] == 1
    assert results["has_next"] is True


def test_autocomplete(seeded_db):
    """Autocomplete returns suggestions matching title prefix."""
    suggestions = SearchService.autocomplete(seeded_db, "Pyt", limit=5)
    assert len(suggestions) > 0
    titles = [s["title"] for s in suggestions]
    assert "Python Programming" in titles


def test_autocomplete_no_match(seeded_db):
    """Autocomplete with non-matching prefix returns empty."""
    suggestions = SearchService.autocomplete(seeded_db, "zzzzz", limit=5)
    assert suggestions == []


def test_autocomplete_short_query(seeded_db):
    """Autocomplete with query under 2 chars returns empty."""
    suggestions = SearchService.autocomplete(seeded_db, "a", limit=5)
    assert suggestions == []


def test_clean_fts_query():
    """clean_fts_query handles various input types."""
    assert SearchService.clean_fts_query("") == ""
    assert SearchService.clean_fts_query("  ") == ""
    assert '"hello world"' in SearchService.clean_fts_query('"hello world"')
    assert SearchService.clean_fts_query("hello") == '"hello"*'
