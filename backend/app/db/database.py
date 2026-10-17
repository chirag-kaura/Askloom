# Askloom starter file: backend/app/db/database.py



from collections.abc import Generator
from urllib.parse import unquote, urlparse

import psycopg
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import NullPool

from backend.app.core.config import DATABASE_URL


def get_connection_details():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is missing. Check backend/.env")

    parsed = urlparse(DATABASE_URL)
    port = parsed.port or 5432

    return {
        "host": parsed.hostname,
        "port": port,
        "dbname": parsed.path.lstrip("/"),
        "user": unquote(parsed.username or ""),
        "password": unquote(parsed.password or ""),
        "connect_timeout": 10,
    }


class Base(DeclarativeBase):
    """Base class for database models."""


# Use QueuePool capped at 10 connections (+5 overflow = max 15) to match Supabase session mode pool.
# prepare_threshold=None disables prepared statements to maintain stability.
# pool_pre_ping=True recycles stale or dropped connections cleanly.
engine: Engine = create_engine(
    "postgresql+psycopg://",
    creator=lambda: psycopg.connect(**get_connection_details(), prepare_threshold=None),
    pool_size=10,
    max_overflow=5,
    pool_timeout=30,
    pool_recycle=300,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_connection() -> None:
    with engine.connect() as connection:
        result = connection.exec_driver_sql("SELECT current_database()")
        print("Supabase connection successful!")
        print("Database:", result.scalar_one())


if __name__ == "__main__":
    test_connection()


