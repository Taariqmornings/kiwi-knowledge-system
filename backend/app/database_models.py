from sqlalchemy import Boolean, Column, Integer, String, DateTime, ForeignKey, Table, Text
from sqlalchemy.orm import relationship
import datetime
from app.core.database import Base

# Association table for many-to-many relationship between Archives and Categories
archive_categories = Table(
    "archive_categories",
    Base.metadata,
    Column("archive_id", String, ForeignKey("archives.id", ondelete="CASCADE"), primary_key=True),
    Column("category_id", Integer, ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True)
)

class Archive(Base):
    __tablename__ = "archives"

    id = Column(String, primary_key=True)  # File hash or unique identifier
    name = Column(String, nullable=False)
    path = Column(String, unique=True, nullable=False)
    title = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    creator = Column(String, nullable=True)
    date = Column(String, nullable=True)
    language = Column(String, nullable=True)
    size_bytes = Column(Integer, nullable=False)
    article_count = Column(Integer, nullable=False)
    status = Column(String, default="idle")  # idle, indexing, paused, indexed, failed, extracting, ready
    indexed_count = Column(Integer, default=0)
    is_extracted = Column(Boolean, default=False)  # True when HTML content is on disk
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    categories = relationship("Category", secondary=archive_categories, back_populates="archives")
    articles = relationship("Article", back_populates="archive", cascade="all, delete-orphan")
    index_jobs = relationship("IndexJob", back_populates="archive", cascade="all, delete-orphan")

class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)
    icon = Column(String, nullable=True)

    # Relationships
    archives = relationship("Archive", secondary=archive_categories, back_populates="categories")

class IndexJob(Base):
    __tablename__ = "index_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    archive_id = Column(String, ForeignKey("archives.id", ondelete="CASCADE"), nullable=False)
    status = Column(String, default="pending", nullable=False)  # pending, running, paused, cancelled, completed, failed
    progress = Column(Integer, default=0)
    total = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    archive = relationship("Archive", back_populates="index_jobs")


class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    archive_id = Column(String, ForeignKey("archives.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=False)
    path = Column(String, nullable=False)  # inner path in ZIM, e.g., A/React_Native.html
    summary = Column(Text, nullable=True)
    keywords = Column(Text, nullable=True)
    mimetype = Column(String, nullable=False)

    # Relationships
    archive = relationship("Archive", back_populates="articles")
