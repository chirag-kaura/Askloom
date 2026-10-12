
from uuid import uuid4

from pydantic import BaseModel, Field


from fastapi import APIRouter, HTTPException

from backend.app.schemas.question import (
    Question,
    QuizGenerationRequest,
    PublicQuestion,
    QuizGenerationResponse,
)
from backend.app.services.llm_service import generate_questions

router = APIRouter(prefix="/quiz", tags=["Quiz"])

# Temporary storage until PostgreSQL is integrated.
quiz_store: dict[str, list[Question]] = {}


@router.post("/generate", response_model=QuizGenerationResponse)
def generate_quiz(request: QuizGenerationRequest):
    """Generate a quiz and keep its answer key on the backend."""
    try:
        questions = generate_questions(
            topic=request.topic,
            difficulty=request.difficulty,
        )

        quiz_id = str(uuid4())
        quiz_store[quiz_id] = questions

        public_questions = [
            PublicQuestion(
                question=question.question,
                options=question.options,
            )
            for question in questions
        ]

        return QuizGenerationResponse(
            quiz_id=quiz_id,
            questions=public_questions,
        )

    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail="Question generation failed. Please try again.",
        ) from exc


class QuizAnswerSubmission(BaseModel):
    quiz_id: str
    selected_answers: list[str | None] = Field(
        min_length=5,
        max_length=5,
    )


@router.post("/submit")
def submit_quiz(submission: QuizAnswerSubmission):
    """Score a completed quiz using the backend's answer key."""
    questions = quiz_store.get(submission.quiz_id)

    if questions is None:
        raise HTTPException(
            status_code=404,
            detail="Quiz not found. Please generate a new quiz.",
        )

    correct_count = sum(
        1
        for question, answer in zip(
            questions,
            submission.selected_answers,
        )
        if answer is not None and answer == question.correct_answer
    )

    total_questions = len(questions)

    return {
        "score": correct_count,
        "total_questions": total_questions,
        "percentage": round((correct_count / total_questions) * 100, 2),
        "correct_count": correct_count,
        "incorrect_count": total_questions - correct_count,
    }
