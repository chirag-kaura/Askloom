


from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.database import Base


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    email: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class QuestionRecord(Base):
    __tablename__ = "questions"

    question_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    option_a: Mapped[str] = mapped_column(Text, nullable=False)
    option_b: Mapped[str] = mapped_column(Text, nullable=False)
    option_c: Mapped[str] = mapped_column(Text, nullable=False)
    option_d: Mapped[str] = mapped_column(Text, nullable=False)
    correct_option: Mapped[str] = mapped_column(String(1), nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    topic: Mapped[str | None] = mapped_column(String, nullable=True)
    difficulty: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Assessment(Base):
    __tablename__ = "assessments"

    assessment_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.user_id"), nullable=False
    )
    difficulty: Mapped[str] = mapped_column(String, nullable=False)
    score: Mapped[int] = mapped_column(
        Integer, server_default="0", nullable=False
    )
    total_questions: Mapped[int] = mapped_column(
        Integer, server_default="5", nullable=False
    )
    status: Mapped[str] = mapped_column(
        String, server_default="in_progress", nullable=False
    )
    started_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[object | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class AssessmentAnswer(Base):
    __tablename__ = "assessment_answers"

    answer_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    assessment_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("assessments.assessment_id"), nullable=False
    )
    slot_number: Mapped[int] = mapped_column(Integer, nullable=False)
    question_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("questions.question_id"), nullable=False
    )
    question_version: Mapped[int] = mapped_column(
        Integer, server_default="1", nullable=False
    )
    regeneration_count: Mapped[int] = mapped_column(
        Integer, server_default="0", nullable=False
    )
    selected_answer: Mapped[str | None] = mapped_column(String(1), nullable=True)
    correct_answer_snapshot: Mapped[str | None] = mapped_column(
        String(1), nullable=True
    )
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    assigned_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    answered_at: Mapped[object | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class QuestionVersionHistory(Base):
    __tablename__ = "question_version_history"

    history_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    assessment_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("assessments.assessment_id"), nullable=False
    )
    slot_number: Mapped[int] = mapped_column(Integer, nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    question_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("questions.question_id"), nullable=False
    )
    assigned_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    discarded_at: Mapped[object | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
