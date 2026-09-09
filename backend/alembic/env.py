import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Add backend directory to sys.path so we can import our models
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.database import Base
from app.database_models import Archive, Category, Article, IndexJob, archive_categories  # noqa: F401

config = context.config

# Ensure migrations always run against the same database the app uses,
# regardless of the process working directory or a DATABASE_PATH override.
from app.core.config import DATABASE_PATH  # noqa: E402
config.set_main_option("sqlalchemy.url", f"sqlite:///{DATABASE_PATH}")

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
