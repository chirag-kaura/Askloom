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