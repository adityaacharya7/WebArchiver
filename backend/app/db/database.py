"""
Database connection and session factory with SQLite WAL mode and foreign key enforcement.
"""
from contextlib import contextmanager
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session
from backend.app.core.config import settings

# Engine configuration
db_url = settings.DATABASE_URL
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

connect_args = {}
if "sqlite" in db_url:
    connect_args = {"check_same_thread": False, "timeout": 30.0}

engine = create_engine(
    db_url,
    connect_args=connect_args,
    echo=False,
    pool_pre_ping=True
)

# SQLite-specific connection pragmas for WAL mode, concurrency & integrity
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if "sqlite" in settings.DATABASE_URL:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)
ScopedSession = scoped_session(SessionLocal)
Base = declarative_base()


def get_db():
    """FastAPI dependency for database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context():
    """Context manager for database sessions in background workers/tasks."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db():
    """Initialize database tables and indexes with automatic schema migrations."""
    from backend.app.db import models  # noqa: F401
    from sqlalchemy import text
    Base.metadata.create_all(bind=engine)

    # Safe migration for existing SQLite databases
    if "sqlite" in settings.DATABASE_URL:
        try:
            with engine.begin() as conn:
                res = conn.execute(text("PRAGMA table_info(urls)")).fetchall()
                existing_cols = {row[1] for row in res}
                if "previous_content_hash" not in existing_cols:
                    conn.execute(text("ALTER TABLE urls ADD COLUMN previous_content_hash VARCHAR(64)"))
                # Safe migration for domains.user_id
                dom_res = conn.execute(text("PRAGMA table_info(domains)")).fetchall()
                dom_cols = {row[1] for row in dom_res}
                if "user_id" not in dom_cols:
                    conn.execute(text("ALTER TABLE domains ADD COLUMN user_id INTEGER REFERENCES users(id)"))
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Database migration note: {e}")

