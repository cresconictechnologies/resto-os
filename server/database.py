"""
RestoOS Production Database Connection & Session Management
Supports dual operation modes:
1. Local Offline LAN: High-performance SQLite WAL + NORMAL sync for zero-latency, power-cut resilience.
2. Supabase / Cloud PostgreSQL: High-availability remote PostgreSQL via Supabase connection pooling.
"""

import os
import shutil
from pathlib import Path
from typing import Generator
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker, DeclarativeBase, Session

# Resolve database path
import sys

if os.getenv("RESTOOS_DATA_DIR"):
    DEFAULT_DB_FILE = Path(os.getenv("RESTOOS_DATA_DIR")) / "restoos.db"
elif getattr(sys, "frozen", False):
    DEFAULT_DB_FILE = Path(sys.executable).parent / "restoos.db"
    if not DEFAULT_DB_FILE.exists():
        bundled_seed = Path(sys._MEIPASS) / "server" / "restoos.db"
        if bundled_seed.exists():
            try:
                shutil.copy2(bundled_seed, DEFAULT_DB_FILE)
            except Exception as e:
                print(f"[RestoOS] Could not seed initial DB: {e}")
else:
    BASE_DIR = Path(__file__).resolve().parent
    DEFAULT_DB_FILE = BASE_DIR / "restoos.db"

# Check for Supabase / PostgreSQL or local SQLite configuration
raw_db_url = os.getenv("SUPABASE_DATABASE_URL") or os.getenv("DATABASE_URL")

if raw_db_url:
    # Normalize postgres:// scheme (used by Supabase / Heroku) to postgresql://
    if raw_db_url.startswith("postgres://"):
        raw_db_url = raw_db_url.replace("postgres://", "postgresql://", 1)
    DATABASE_URL = raw_db_url
else:
    # On Serverless platforms like Vercel, root filesystem is read-only.
    # If no remote Supabase is configured yet, fall back to writable /tmp directory.
    if os.getenv("VERCEL") == "1" or os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
        tmp_db = Path("/tmp/restoos.db")
        if not tmp_db.exists() and DEFAULT_DB_FILE.exists():
            try:
                shutil.copy2(DEFAULT_DB_FILE, tmp_db)
            except Exception as e:
                print(f"[RestoOS] Notice: Could not copy seed DB to /tmp: {e}")
        DATABASE_URL = f"sqlite:///{tmp_db}"
    else:
        DATABASE_URL = f"sqlite:///{DEFAULT_DB_FILE}"

is_sqlite = "sqlite" in DATABASE_URL

# SQLAlchemy 2.0 Engine Configuration
if is_sqlite:
    engine = create_engine(
        DATABASE_URL,
        connect_args={
            "check_same_thread": False,
            "timeout": 30,  # 30-second lock timeout for busy write queues
        },
        echo=os.getenv("SQL_ECHO", "False").lower() in ("true", "1"),
    )

    # Enforce SQLite WAL Mode, Power-cut Safety, and Foreign Key Integrity
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.execute("PRAGMA temp_store=MEMORY;")
        cursor.execute("PRAGMA busy_timeout=5000;")
        cursor.close()

else:
    # PostgreSQL / Supabase connection handling
    # On Serverless runtimes (Vercel / AWS Lambda), use NullPool to prevent connection starvation on Supabase.
    is_serverless = os.getenv("VERCEL") == "1" or bool(os.getenv("AWS_LAMBDA_FUNCTION_NAME"))
    if is_serverless:
        from sqlalchemy.pool import NullPool
        engine = create_engine(
            DATABASE_URL,
            poolclass=NullPool,
            echo=os.getenv("SQL_ECHO", "False").lower() in ("true", "1"),
        )
    else:
        engine = create_engine(
            DATABASE_URL,
            pool_pre_ping=True,
            pool_size=int(os.getenv("DB_POOL_SIZE", "10")),
            max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "20")),
            echo=os.getenv("SQL_ECHO", "False").lower() in ("true", "1"),
        )

# Session Factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)

# Declarative Base for all models
class Base(DeclarativeBase):
    pass

# FastAPI & Worker dependency generator
def get_db() -> Generator[Session, None, None]:
    """Dependency session generator providing transaction scope with automatic rollback on error."""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
