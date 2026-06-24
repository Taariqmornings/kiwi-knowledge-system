import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker
from app.core.config import DATABASE_PATH

# Connect to the SQLite database
# Using check_same_thread=False since FastAPI handles multiple threads
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False
)

# SQLite-specific performance tuning:
# - WAL (Write-Ahead Logging) mode allows simultaneous reads while indexing in the background
# - SYNCHRONOUS = NORMAL is safe for WAL and much faster
# - FOREIGN KEYS = ON enforces relational constraints
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    # 30-second busy timeout lets concurrent indexer threads wait their turn
    # instead of erroring out with "database is locked".
    cursor.execute("PRAGMA busy_timeout=30000")
    cursor.execute("PRAGMA cache_size=-20000")  # ~20MB page cache per connection
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """Dependency helper to get a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
