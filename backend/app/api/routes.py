# Askloom starter file: backend/app/api/routes.py

from fastapi import APIRouter, HTTPException

from backend.app.schemas.question import (
    Question,
    QuizGenerationRequest,
)
from backend.app.services.llm_service import generate_questions

router = APIRouter(prefix="/quiz", tags=["Quiz"])


@router.post("/generate", response_model=list[Question])
def generate_quiz(request: QuizGenerationRequest):
    """Generate five quiz questions for the requested topic."""
    try:
        return generate_questions(
            topic=request.topic,
            difficulty=request.difficulty,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail="Question generation failed. Please try again.",
        ) from exc
