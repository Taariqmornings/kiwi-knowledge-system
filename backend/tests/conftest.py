"""
Pytest configuration with test database and FastAPI test client.
Uses an isolated in-memory SQLite database to avoid side effects.
"""
import sys
import os
from pathlib import Path

# Ensure the backend directory is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.core.database import Base, get_db
from app.main import app


@pytest.fixture(scope="session")
def test_engine():
    """Create an in-memory SQLite engine for testing."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Create all tables
    Base.metadata.create_all(bind=engine)
    # Create FTS5 virtual table
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts USING fts5("
            "title, summary, keywords, "
            "tokenize='unicode61'"
            ")"
        ))
    # Seed categories
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT OR IGNORE INTO categories (name, icon) VALUES "
            "('Medicine', 'HeartPulse'), ('Science', 'Atom'), ('Engineering', 'Cpu'), "
            "('History', 'BookOpen'), ('Geography', 'Globe'), ('Coding', 'Code'), "
            "('Mathematics', 'Calculator'), ('Survival', 'Flame'), "
            "('Education', 'GraduationCap'), ('General Knowledge', 'Library')"
        ))
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(test_engine):
    """Create a fresh database session for each test with rollback isolation."""
    connection = test_engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(autocommit=False, autoflush=False, bind=connection)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db_session):
    """FastAPI test client with overridden database dependency."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def sample_archive(db_session):
    """Insert a minimal archive into the test database."""
    from app.database_models import Archive
    archive = Archive(
        id="test-archive-001",
        name="test.zim",
        path="/tmp/test.zim",
        title="Test Archive",
        description="A test archive for unit tests",
        creator="Test Author",
        date="2024-01-01",
        language="eng",
        size_bytes=1000,
        article_count=10,
        status="idle",
        indexed_count=0,
    )
    db_session.add(archive)
    db_session.commit()
    return archive
