

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.database import get_db
from backend.app.models import (
    Assessment,
    AssessmentAnswer,
    QuestionRecord,
    User,
)
from backend.app.schemas.question import (
    PublicQuestion,
    QuizGenerationRequest,
    QuizGenerationResponse,
)
from backend.app.services.llm_service import generate_questions

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/quiz", tags=["Quiz"])

def get_authenticated_user_id(request: Request) -> int:
    """Return the database ID of the authenticated user."""
    user = request.session.get("user")

    if not user or not user.get("user_id"):
        raise HTTPException(
            status_code=401,
            detail="Please sign in to continue.",
        )

    return int(user["user_id"])


class QuizAnswerSubmission(BaseModel):
    quiz_id: int
    selected_answers: list[str | None] = Field(
        min_length=5,
        max_length=5,
    )


@router.post("/generate", response_model=QuizGenerationResponse)
def generate_quiz(
    quiz_request: QuizGenerationRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Generate five questions for the authenticated user."""
    user_id = get_authenticated_user_id(request)
    user = db.get(User, user_id)

    if user is None:
        request.session.clear()
        raise HTTPException(
            status_code=401,
            detail="User account not found. Please sign in again.",
        )

    try:
        generated_questions = generate_questions(
            topic=quiz_request.topic,
            difficulty=quiz_request.difficulty,
        )

        assessment = Assessment(
            user_id=user.user_id,
            difficulty=quiz_request.difficulty,
            total_questions=5,
            status="in_progress",
        )
        db.add(assessment)
        db.flush()

        public_questions = []

        for slot_number, generated in enumerate(generated_questions, start=1):
            # Store answer choices as A, B, C, D so the database can
            # record a compact answer key and submitted option consistently.
            question_record = QuestionRecord(
                question_text=generated.question,
                option_a=generated.options[0],
                option_b=generated.options[1],
                option_c=generated.options[2],
                option_d=generated.options[3],
                correct_option=chr(65 + generated.options.index(generated.correct_answer)),
                explanation=generated.explanation,
                topic=quiz_request.topic,
                difficulty=quiz_request.difficulty,
            )
            db.add(question_record)
            db.flush()

            db.add(
                AssessmentAnswer(
                    assessment_id=assessment.assessment_id,
                    slot_number=slot_number,
                    question_id=question_record.question_id,
                    question_version=1,
                    regeneration_count=0,
                    correct_answer_snapshot=question_record.correct_option,
                )
            )

            public_questions.append(
                PublicQuestion(
                    question=generated.question,
                    options=generated.options,
                )
            )

        db.commit()

        return QuizGenerationResponse(
            quiz_id=str(assessment.assessment_id),
            questions=public_questions,
        )

    except HTTPException:
        db.rollback()
        raise
    
    except Exception as exc:
       # import logging

        logger.exception("Quiz generation or database saving failed")
        db.rollback()
        logger.exception("Quiz generation or database saving failed")

        raise HTTPException(
        status_code=502,
        detail="Question generation or database saving failed. Please try again.",
    ) from exc


@router.post("/submit")
def submit_quiz(
    submission: QuizAnswerSubmission,
    request: Request,
    db: Session = Depends(get_db),
):
    """Score a quiz using stored answer keys and save the result."""
    assessment = db.get(Assessment, submission.quiz_id)

    if assessment is None:
        raise HTTPException(status_code=404, detail="Quiz not found.")

    if assessment.user_id != DEV_USER_ID:
        raise HTTPException(status_code=403, detail="Quiz does not belong to this user.")

    # 3. Prevent duplicate submissions.
    if assessment.status != "in_progress":
        raise HTTPException(
            status_code=409,
            detail="This quiz has already been submitted.",
        )

    # 4. Retrieve all five answer records in question order.
    answers = db.scalars(
        select(AssessmentAnswer)
        .where(
            AssessmentAnswer.assessment_id == assessment.assessment_id
        )
        .order_by(AssessmentAnswer.slot_number)
    ).all()

    if len(answers) != 5:
        raise HTTPException(
            status_code=409,
            detail="This quiz does not contain exactly five questions.",
        )

    valid_options = {"A", "B", "C", "D"}
    correct_count = 0
    submitted_at = datetime.now(timezone.utc)

    # 5. Validate and save the user's five answers.
    for answer_record, selected in zip(
        answers, submission.selected_answers
    ):
        selected_letter = None

        if selected is not None:
            normalized = selected.strip()

            if normalized.upper() in valid_options:
                selected_letter = normalized.upper()
            else:
                question = db.get(
                    QuestionRecord, answer_record.question_id
                )

                option_map = {
                    "A": question.option_a,
                    "B": question.option_b,
                    "C": question.option_c,
                    "D": question.option_d,
                }

                selected_letter = next(
                    (
                        letter
                        for letter, option_text in option_map.items()
                        if option_text == normalized
                    ),
                    None,
                )

            if selected_letter is None:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        "Each answer must be A, B, C, D, "
                        "or an exact displayed option."
                    ),
                )

        answer_record.selected_answer = selected_letter
        answer_record.is_correct = (
            selected_letter == answer_record.correct_answer_snapshot
            if selected_letter is not None
            else False
        )
        answer_record.answered_at = submitted_at

        if answer_record.is_correct:
            correct_count += 1

    # 6. Update the assessment summary.
    total_questions = len(answers)

    assessment.score = correct_count
    assessment.status = "completed"
    assessment.completed_at = submitted_at

    # 7. Save the submission before returning correct answers.
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Could not save quiz submission.",
        ) from exc

    # 8. Build the detailed review from stored database records.
    question_reviews = []

    for answer_record in answers:
        question = db.get(
            QuestionRecord, answer_record.question_id
        )

        if question is None:
            raise HTTPException(
                status_code=500,
                detail="A question record could not be found.",
            )

        option_map = {
            "A": question.option_a,
            "B": question.option_b,
            "C": question.option_c,
            "D": question.option_d,
        }

        correct_letter = answer_record.correct_answer_snapshot
        selected_letter = answer_record.selected_answer

        options = [
            {
                "label": letter,
                "text": option_text,
                "is_correct": letter == correct_letter,
                "is_selected": letter == selected_letter,
            }
            for letter, option_text in option_map.items()
        ]

        question_reviews.append(
            {
                "question_number": answer_record.slot_number,
                "question": question.question_text,
                "options": options,
                "selected_answer": selected_letter,
                "selected_answer_text": (
                    option_map.get(selected_letter)
                    if selected_letter is not None
                    else None
                ),
                "correct_answer": correct_letter,
                "correct_answer_text": option_map[correct_letter],
                "is_correct": bool(answer_record.is_correct),
                "explanation": question.explanation,
            }
        )

    # 9. Return the summary and all five question reviews.
    return {
        "quiz_id": assessment.assessment_id,
        "score": correct_count,
        "total_questions": total_questions,
        "percentage": round(
            correct_count / total_questions * 100, 2
        ),
        "correct_count": correct_count,
        "incorrect_count": total_questions - correct_count,
        "questions": question_reviews,
    }
