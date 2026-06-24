"""fts_triggers_and_indexes

Converts articles_fts from a standalone FTS5 table to a content-backed table
linked to the articles table, then adds SQLite triggers so FTS stays in sync
automatically. Also adds composite indexes for common query patterns.

Revision ID: e7f8a9b0c1d2
Revises: 493e0919be97
Create Date: 2026-05-27 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op


revision: str = 'e7f8a9b0c1d2'
down_revision: Union[str, Sequence[str], None] = '493e0919be97'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop standalone FTS table (recreated as content-backed below)
    op.execute("DROP TABLE IF EXISTS articles_fts")

    # Content-backed FTS5 table: stores only the inverted index; actual text
    # is read from the articles table via content_rowid=id. This halves
    # storage and prevents FTS/articles divergence.
    op.execute("""
        CREATE VIRTUAL TABLE articles_fts USING fts5(
            title, summary, keywords,
            content='articles',
            content_rowid='id',
            tokenize='unicode61'
        )
    """)

    # INSERT trigger: fires when a new article row is written
    op.execute("""
        CREATE TRIGGER IF NOT EXISTS articles_ai
        AFTER INSERT ON articles BEGIN
            INSERT INTO articles_fts(rowid, title, summary, keywords)
            VALUES (new.id, new.title, new.summary, new.keywords);
        END
    """)

    # DELETE trigger: fires when an article row is removed
    op.execute("""
        CREATE TRIGGER IF NOT EXISTS articles_ad
        AFTER DELETE ON articles BEGIN
            INSERT INTO articles_fts(articles_fts, rowid, title, summary, keywords)
            VALUES ('delete', old.id, old.title, old.summary, old.keywords);
        END
    """)

    # UPDATE trigger: re-indexes changed article text
    op.execute("""
        CREATE TRIGGER IF NOT EXISTS articles_au
        AFTER UPDATE ON articles BEGIN
            INSERT INTO articles_fts(articles_fts, rowid, title, summary, keywords)
            VALUES ('delete', old.id, old.title, old.summary, old.keywords);
            INSERT INTO articles_fts(rowid, title, summary, keywords)
            VALUES (new.id, new.title, new.summary, new.keywords);
        END
    """)

    # Rebuild FTS index from any articles already in the database
    op.execute("INSERT INTO articles_fts(articles_fts) VALUES('rebuild')")

    # --- Performance indexes ---
    # Most queries filter by archive_id; this index is used by search, cancel, delete
    op.execute("CREATE INDEX IF NOT EXISTS idx_articles_archive_id ON articles(archive_id)")
    # Path lookups for article retrieval
    op.execute("CREATE INDEX IF NOT EXISTS idx_articles_archive_path ON articles(archive_id, path)")
    # Job status polling
    op.execute("CREATE INDEX IF NOT EXISTS idx_jobs_archive_status ON index_jobs(archive_id, status)")
    # Category filtering in search queries
    op.execute("CREATE INDEX IF NOT EXISTS idx_archive_categories_archive ON archive_categories(archive_id)")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS articles_ai")
    op.execute("DROP TRIGGER IF EXISTS articles_ad")
    op.execute("DROP TRIGGER IF EXISTS articles_au")
    op.execute("DROP TABLE IF EXISTS articles_fts")

    # Restore standalone FTS table (no auto-sync, manual maintenance required)
    op.execute("""
        CREATE VIRTUAL TABLE articles_fts USING fts5(
            title, summary, keywords,
            tokenize='unicode61'
        )
    """)

    op.execute("DROP INDEX IF EXISTS idx_articles_archive_id")
    op.execute("DROP INDEX IF EXISTS idx_articles_archive_path")
    op.execute("DROP INDEX IF EXISTS idx_jobs_archive_status")
    op.execute("DROP INDEX IF EXISTS idx_archive_categories_archive")
