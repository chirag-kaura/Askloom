# Askloom starter file: backend/app/db/database.py



from collections.abc import Generator
from urllib.parse import unquote, urlparse

import psycopg
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.app.core.config import DATABASE_URL


def get_connection_details():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is missing. Check backend/.env")

    parsed = urlparse(DATABASE_URL)

    return {
        "host": parsed.hostname,
        "port": parsed.port or 5432,
        "dbname": parsed.path.lstrip("/"),
        "user": unquote(parsed.username or ""),
        "password": unquote(parsed.password or ""),
        "connect_timeout": 10,
    }


class Base(DeclarativeBase):
    """Base class for database models."""


engine: Engine = create_engine(
    "postgresql+psycopg://",
    creator=lambda: psycopg.connect(**get_connection_details()),
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


