

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.db.database import get_db
from backend.app.models import (
    Assessment,
    AssessmentAnswer,
    QuestionRecord,
    QuestionVersionHistory,
    User,
)
from backend.app.schemas.question import (
    PublicQuestion,
    QuizGenerationRequest,
    QuizGenerationResponse,
)
import inspect
import logging

from starlette.concurrency import run_in_threadpool

from backend.app.services.guardrails import validate_topic_guardrails
from backend.app.services.llm_service import generate_questions

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


def get_optional_user_id(request: Request) -> int | None:
    """Return the database ID of the user if authenticated, otherwise None."""
    user = request.session.get("user")
    if user and user.get("user_id"):
        return int(user["user_id"])
    return None


class QuizAnswerSubmission(BaseModel):
    quiz_id: int
    selected_answers: list[str | None] = Field(
        min_length=5,
        max_length=5,
    )


class QuizAlternateRequest(BaseModel):
    quiz_id: int
    slot_number: int = Field(ge=1, le=5)


def _save_generated_quiz(db: Session, user_id: int, difficulty: str, sanitized_topic: str, generated_questions: list):
    """Save newly generated assessment and questions to DB in worker threadpool."""
    user = db.get(User, user_id)
    if user is None:
        return None, None

    assessment = Assessment(
        user_id=user.user_id,
        difficulty=difficulty,
        total_questions=5,
        status="in_progress",
    )
    db.add(assessment)
    db.flush()

    public_questions = []

    for slot_number, generated in enumerate(generated_questions, start=1):
        question_record = QuestionRecord(
            question_text=generated.question,
            option_a=generated.options[0],
            option_b=generated.options[1],
            option_c=generated.options[2],
            option_d=generated.options[3],
            correct_option=chr(65 + generated.options.index(generated.correct_answer)),
            explanation=generated.explanation,
            topic=sanitized_topic,
            difficulty=difficulty,
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

        db.add(
            QuestionVersionHistory(
                assessment_id=assessment.assessment_id,
                slot_number=slot_number,
                version_number=1,
                question_id=question_record.question_id,
                assigned_at=datetime.now(timezone.utc),
            )
        )

        public_questions.append(
            PublicQuestion(
                question=generated.question,
                options=generated.options,
            )
        )

    db.commit()
    return assessment.assessment_id, public_questions


@router.post("/generate", response_model=QuizGenerationResponse)
async def generate_quiz(
    quiz_request: QuizGenerationRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Generate five questions for the authenticated user."""
    user_id = get_authenticated_user_id(request)

    # 1. Enforce input grounding and prompt injection guardrails
    sanitized_topic = validate_topic_guardrails(quiz_request.topic)

    try:
        gen_result = generate_questions(
            topic=sanitized_topic,
            difficulty=quiz_request.difficulty,
        )
        if inspect.isawaitable(gen_result):
            generated_questions = await gen_result
        else:
            generated_questions = gen_result

        assessment_id, public_questions = await run_in_threadpool(
            _save_generated_quiz,
            db,
            user_id,
            quiz_request.difficulty,
            sanitized_topic,
            generated_questions,
        )

        if assessment_id is None:
            request.session.clear()
            raise HTTPException(
                status_code=401,
                detail="User account not found. Please sign in again.",
            )

        return QuizGenerationResponse(
            quiz_id=str(assessment_id),
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
    user_id = get_authenticated_user_id(request)

    assessment = db.get(Assessment, submission.quiz_id)

    if assessment is None:
        raise HTTPException(status_code=404, detail="Quiz not found.")

    if assessment.user_id != user_id:
        raise HTTPException(
            status_code=403,
            detail="Quiz does not belong to this user.",
        )

    # 3. Prevent duplicate submissions.
    if assessment.status != "in_progress":
        raise HTTPException(
            status_code=409,
            detail="This quiz has already been submitted.",
        )

    # 4. Retrieve all five answer records and questions in question order in a single query.
    answer_rows = db.execute(
        select(AssessmentAnswer, QuestionRecord)
        .join(QuestionRecord, QuestionRecord.question_id == AssessmentAnswer.question_id)
        .where(AssessmentAnswer.assessment_id == assessment.assessment_id)
        .order_by(AssessmentAnswer.slot_number)
    ).all()

    if len(answer_rows) != 5:
        raise HTTPException(
            status_code=409,
            detail="This quiz does not contain exactly five questions.",
        )

    valid_options = {"A", "B", "C", "D"}
    correct_count = 0
    submitted_at = datetime.now(timezone.utc)

    # 5. Validate and save the user's five answers.
    for (answer_record, question), selected in zip(
        answer_rows, submission.selected_answers
    ):
        selected_letter = None

        if selected is not None:
            normalized = selected.strip()

            if normalized.upper() in valid_options:
                selected_letter = normalized.upper()
            else:
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
    total_questions = len(answer_rows)

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

    # 8. Build the detailed review directly without additional database queries.
    question_reviews = []

    for answer_record, question in answer_rows:
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


@router.get("/stats")
def get_quiz_stats(
    request: Request,
    db: Session = Depends(get_db),
):
    """Return learning statistics for the current user or guest defaults."""
    user_id = get_optional_user_id(request)
    if not user_id:
        return {
            "authenticated": False,
            "total_assessments": 0,
            "completed_assessments": 0,
            "average_score": None,
            "total_questions_answered": 0,
            "favorite_topic": "None",
        }

    # Fetch all assessments and their primary topic in ONE query instead of N+1 queries
    rows = db.execute(
        select(Assessment, QuestionRecord.topic)
        .outerjoin(
            AssessmentAnswer,
            (AssessmentAnswer.assessment_id == Assessment.assessment_id)
            & (AssessmentAnswer.slot_number == 1),
        )
        .outerjoin(
            QuestionRecord,
            QuestionRecord.question_id == AssessmentAnswer.question_id,
        )
        .where(Assessment.user_id == user_id)
    ).all()

    total = len(rows)
    completed = [a for a, _ in rows if a.status == "completed"]
    completed_count = len(completed)

    avg_score = None
    if completed_count > 0:
        percentages = [
            (a.score / a.total_questions * 100)
            for a in completed
            if a.total_questions > 0
        ]
        avg_score = round(sum(percentages) / len(percentages), 1) if percentages else 0.0

    topic_counts: dict[str, int] = {}
    total_questions = 0

    for a, topic in rows:
        total_questions += a.total_questions
        if topic:
            topic_counts[topic] = topic_counts.get(topic, 0) + 1

    favorite_topic = max(topic_counts, key=topic_counts.get) if topic_counts else "General Knowledge"

    return {
        "authenticated": True,
        "total_assessments": total,
        "completed_assessments": completed_count,
        "average_score": avg_score,
        "total_questions_answered": total_questions,
        "favorite_topic": favorite_topic,
    }


@router.get("/history")
def get_quiz_history(
    request: Request,
    db: Session = Depends(get_db),
):
    """Return full assessment history for the authenticated user."""
    user_id = get_optional_user_id(request)
    if not user_id:
        return {"authenticated": False, "assessments": []}

    rows = db.execute(
        select(Assessment, QuestionRecord.topic)
        .outerjoin(
            AssessmentAnswer,
            (AssessmentAnswer.assessment_id == Assessment.assessment_id)
            & (AssessmentAnswer.slot_number == 1),
        )
        .outerjoin(
            QuestionRecord,
            QuestionRecord.question_id == AssessmentAnswer.question_id,
        )
        .where(Assessment.user_id == user_id)
        .order_by(Assessment.started_at.desc())
    ).all()

    history = []
    for a, topic in rows:
        pct = round((a.score / a.total_questions * 100), 1) if a.total_questions > 0 else 0.0
        history.append({
            "assessment_id": a.assessment_id,
            "topic": topic or "General Knowledge",
            "difficulty": a.difficulty,
            "score": a.score,
            "total_questions": a.total_questions,
            "percentage": pct,
            "status": a.status,
            "started_at": a.started_at.isoformat() if a.started_at else None,
            "completed_at": a.completed_at.isoformat() if a.completed_at else None,
        })

    return {"authenticated": True, "assessments": history}


@router.get("/review/{quiz_id}")
def get_quiz_review(
    quiz_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Retrieve full review and question breakdown for a past assessment."""
    user_id = get_authenticated_user_id(request)

    assessment = db.get(Assessment, quiz_id)
    if assessment is None:
        raise HTTPException(status_code=404, detail="Quiz not found.")

    if assessment.user_id != user_id:
        raise HTTPException(status_code=403, detail="Quiz does not belong to this user.")

    rows = db.execute(
        select(AssessmentAnswer, QuestionRecord)
        .join(QuestionRecord, QuestionRecord.question_id == AssessmentAnswer.question_id)
        .where(AssessmentAnswer.assessment_id == assessment.assessment_id)
        .order_by(AssessmentAnswer.slot_number)
    ).all()

    question_reviews = []
    topic = "General Knowledge"

    for answer_record, question in rows:
        if question and question.topic:
            topic = question.topic

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

        question_reviews.append({
            "question_number": answer_record.slot_number,
            "question": question.question_text,
            "options": options,
            "selected_answer": selected_letter,
            "selected_answer_text": option_map.get(selected_letter) if selected_letter else None,
            "correct_answer": correct_letter,
            "correct_answer_text": option_map.get(correct_letter),
            "is_correct": bool(answer_record.is_correct),
            "explanation": question.explanation,
        })

    total_questions = len(rows) or assessment.total_questions
    return {
        "quiz_id": assessment.assessment_id,
        "topic": topic,
        "difficulty": assessment.difficulty,
        "score": assessment.score,
        "total_questions": total_questions,
        "percentage": round(assessment.score / total_questions * 100, 1) if total_questions else 0.0,
        "correct_count": assessment.score,
        "incorrect_count": total_questions - assessment.score,
        "status": assessment.status,
        "started_at": assessment.started_at.isoformat() if assessment.started_at else None,
        "completed_at": assessment.completed_at.isoformat() if assessment.completed_at else None,
        "questions": question_reviews,
    }


@router.get("/resume/{quiz_id}")
def resume_quiz(
    quiz_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Resume an in-progress assessment and return its active questions without spoiling answers."""
    user_id = get_authenticated_user_id(request)

    assessment = db.get(Assessment, quiz_id)
    if assessment is None:
        raise HTTPException(status_code=404, detail="Quiz not found.")

    if assessment.user_id != user_id:
        raise HTTPException(status_code=403, detail="Quiz does not belong to this user.")

    if assessment.status != "in_progress":
        raise HTTPException(status_code=409, detail="This quiz has already been completed.")

    answer_rows = db.execute(
        select(AssessmentAnswer, QuestionRecord)
        .join(QuestionRecord, QuestionRecord.question_id == AssessmentAnswer.question_id)
        .where(AssessmentAnswer.assessment_id == assessment.assessment_id)
        .order_by(AssessmentAnswer.slot_number)
    ).all()

    if not answer_rows:
        raise HTTPException(status_code=404, detail="No questions found for this quiz.")

    public_questions = []
    selected_answers = []
    topic = "General Knowledge"

    for answer_record, question in answer_rows:
        if question.topic:
            topic = question.topic
        options = [question.option_a, question.option_b, question.option_c, question.option_d]
        public_questions.append({
            "question": question.question_text,
            "options": options,
        })
        selected_answers.append(answer_record.selected_answer)

    # Count total alternate questions used across this assessment
    alternates_used = db.execute(
        select(func.count(QuestionVersionHistory.history_id))
        .where(
            QuestionVersionHistory.assessment_id == assessment.assessment_id,
            QuestionVersionHistory.version_number > 1,
        )
    ).scalar() or 0

    alternates_remaining = max(0, 3 - alternates_used)

    return {
        "quiz_id": assessment.assessment_id,
        "topic": topic,
        "difficulty": assessment.difficulty,
        "questions": public_questions,
        "selected_answers": selected_answers,
        "total_questions": len(public_questions),
        "alternates_remaining": alternates_remaining,
    }


@router.post("/alternate")
async def generate_alternate_question(
    alternate_req: QuizAlternateRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Generate an alternate question for an active question slot (up to 3 per assessment)."""
    user_id = get_authenticated_user_id(request)

    assessment = db.get(Assessment, alternate_req.quiz_id)
    if assessment is None:
        raise HTTPException(status_code=404, detail="Quiz not found.")

    if assessment.user_id != user_id:
        raise HTTPException(status_code=403, detail="Quiz does not belong to this user.")

    if assessment.status != "in_progress":
        raise HTTPException(status_code=409, detail="This quiz has already been completed.")

    # 1. Check assessment-level alternate quota (max 3 total across quiz)
    total_alternates_used = db.execute(
        select(func.count(QuestionVersionHistory.history_id))
        .where(
            QuestionVersionHistory.assessment_id == assessment.assessment_id,
            QuestionVersionHistory.version_number > 1,
        )
    ).scalar() or 0

    if total_alternates_used >= 3:
        raise HTTPException(
            status_code=400,
            detail="You have used all 3 alternate questions for this assessment.",
        )

    # 2. Check slot-level answer record
    answer_record = db.execute(
        select(AssessmentAnswer)
        .where(
            AssessmentAnswer.assessment_id == assessment.assessment_id,
            AssessmentAnswer.slot_number == alternate_req.slot_number,
        )
    ).scalar_one_or_none()

    if answer_record is None:
        raise HTTPException(status_code=404, detail="Question slot not found.")

    if answer_record.question_version >= 3:
        raise HTTPException(
            status_code=400,
            detail="This question slot has reached its maximum version limit (3).",
        )

    # 3. Retrieve original topic and difficulty from current question
    current_question = db.get(QuestionRecord, answer_record.question_id)
    topic = current_question.topic if current_question and current_question.topic else "General Knowledge"
    difficulty = assessment.difficulty or (current_question.difficulty if current_question else "Medium")

    # 4. Generate new question via LLM (or curated pool)
    try:
        gen_result = generate_questions(topic=topic, difficulty=difficulty)
        if inspect.isawaitable(gen_result):
            new_questions = await gen_result
        else:
            new_questions = gen_result

        # Pick one question that differs from the current question text
        new_q_obj = None
        for q in new_questions:
            if current_question and q.question.strip() == current_question.question_text.strip():
                continue
            new_q_obj = q
            break
        if not new_q_obj:
            new_q_obj = new_questions[0]

        # 5. Save new question record in DB
        new_question_record = QuestionRecord(
            question_text=new_q_obj.question,
            option_a=new_q_obj.options[0],
            option_b=new_q_obj.options[1],
            option_c=new_q_obj.options[2],
            option_d=new_q_obj.options[3],
            correct_option=chr(65 + new_q_obj.options.index(new_q_obj.correct_answer)),
            explanation=new_q_obj.explanation,
            topic=topic,
            difficulty=difficulty,
        )
        db.add(new_question_record)
        db.flush()

        # 6. Mark previous active version row as discarded
        prev_history = db.execute(
            select(QuestionVersionHistory)
            .where(
                QuestionVersionHistory.assessment_id == assessment.assessment_id,
                QuestionVersionHistory.slot_number == alternate_req.slot_number,
                QuestionVersionHistory.discarded_at.is_(None),
            )
        ).scalar_one_or_none()

        now = datetime.now(timezone.utc)
        if prev_history:
            prev_history.discarded_at = now

        new_version = answer_record.question_version + 1

        # 7. Add new QuestionVersionHistory record
        new_history = QuestionVersionHistory(
            assessment_id=assessment.assessment_id,
            slot_number=alternate_req.slot_number,
            version_number=new_version,
            question_id=new_question_record.question_id,
            assigned_at=now,
        )
        db.add(new_history)

        # 8. Update AssessmentAnswer for this slot
        answer_record.question_id = new_question_record.question_id
        answer_record.question_version = new_version
        answer_record.regeneration_count = (answer_record.regeneration_count or 0) + 1
        answer_record.correct_answer_snapshot = new_question_record.correct_option
        answer_record.selected_answer = None
        answer_record.is_correct = None
        answer_record.assigned_at = now
        answer_record.answered_at = None

        db.commit()

        alternates_remaining = max(0, 3 - (total_alternates_used + 1))

        return {
            "quiz_id": assessment.assessment_id,
            "slot_number": alternate_req.slot_number,
            "version_number": new_version,
            "alternates_remaining": alternates_remaining,
            "question": {
                "question": new_question_record.question_text,
                "options": [
                    new_question_record.option_a,
                    new_question_record.option_b,
                    new_question_record.option_c,
                    new_question_record.option_d,
                ],
            },
        }

    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("Alternate question generation failed")
        raise HTTPException(
            status_code=502,
            detail="Failed to generate alternate question. Please try again.",
        ) from exc
