"""Initialize an isolated PostgreSQL database for the test suite."""

import pytest
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert

from backend.app.db.database import Base, engine
from backend.app.models import (
    Assessment,
    AssessmentAnswer,
    QuestionRecord,
    QuestionVersionHistory,
    User,
)


@pytest.fixture(scope="session", autouse=True)
def initialize_test_database():
    """Create test tables and seed the users expected by integration tests."""
    Base.metadata.create_all(bind=engine)

    with engine.begin() as connection:
        connection.execute(
            text("""
                INSERT INTO users (user_id, email)
                OVERRIDING SYSTEM VALUE
                VALUES
                    (1, 'askloom-dev@example.com'),
                    (2, 'other@example.com')
                ON CONFLICT (user_id) DO NOTHING
            """)
        )

        connection.execute(
            text("""
                SELECT setval(
                    pg_get_serial_sequence('users', 'user_id'),
                    GREATEST(COALESCE((SELECT MAX(user_id) FROM users), 1), 2),
                    true
                )
            """)
        )

    yield

    Base.metadata.drop_all(bind=engine)
    engine.dispose()
