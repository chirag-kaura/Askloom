# Askloom starter file: backend/app/schemas/question.py

from pydantic import BaseModel, Field

from typing import Literal


class Question(BaseModel):
    question: str = Field(min_length=1)
    options: list[str] = Field(min_length=4, max_length=4)
    correct_answer: str
    explanation: str = Field(min_length=1)


class QuizGenerationRequest(BaseModel):
    topic: str = Field(
        default="General Knowledge",
        min_length=1,
        max_length=100,
    )
    difficulty: Literal["Easy", "Medium", "Hard"] = "Medium"


class QuizSubmission(BaseModel):
    questions: list[Question] = Field(min_length=5, max_length=5)
    selected_answers: list[str | None] = Field(min_length=5, max_length=5)


class QuizScoreResponse(BaseModel):
    score: int = Field(ge=0, le=5)
    total_questions: int = Field(default=5, ge=5, le=5)
    percentage: float = Field(ge=0, le=100)
    correct_count: int = Field(ge=0, le=5)
    incorrect_count: int = Field(ge=0, le=5)


class PublicQuestion(BaseModel):
    question: str = Field(min_length=1)
    options: list[str] = Field(min_length=4, max_length=4)


class QuizGenerationResponse(BaseModel):
    quiz_id: str
    questions: list[PublicQuestion] = Field(min_length=5, max_length=5)