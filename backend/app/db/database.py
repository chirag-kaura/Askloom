# Askloom starter file: backend/app/db/database.py

from collections.abc import Generator
from urllib.parse import parse_qsl, unquote, urlparse

import psycopg
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import NullPool

from backend.app.core.config import DATABASE_URL


def get_connection_details():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is missing. Check backend/.env")

    clean_url = DATABASE_URL.strip().strip('"').strip("'")
    parsed = urlparse(clean_url)
    port = parsed.port or 5432
    query_params = dict(parse_qsl(parsed.query))

    details = {
        "host": parsed.hostname,
        "port": port,
        "dbname": parsed.path.lstrip("/"),
        "user": unquote(parsed.username or ""),
        "password": unquote(parsed.password or ""),
        "connect_timeout": 10,
    }

    if "sslmode" in query_params:
        details["sslmode"] = query_params["sslmode"]
    elif parsed.hostname and ("supabase" in parsed.hostname or "render" in parsed.hostname):
        details["sslmode"] = "require"

    return details


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
