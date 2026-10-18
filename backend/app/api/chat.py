# Askloom: backend/app/api/chat.py

import json
import logging
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.database import get_db
from backend.app.models import Assessment, AssessmentAnswer, QuestionRecord, User
from backend.app.services.chat_service import ChatService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["AI Assistant"])


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str = Field(min_length=1, max_length=4000)


class ChatContext(BaseModel):
    quiz_id: Optional[int] = None
    question_number: Optional[int] = None
    question_text: Optional[str] = None
    options: Optional[list[str]] = None
    selected_answer: Optional[str] = None
    correct_answer: Optional[str] = None
    explanation: Optional[str] = None
    topic: Optional[str] = None
    difficulty: Optional[str] = None


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    mode: Literal["socratic_hint", "deep_dive_review", "tutor_general"] = "tutor_general"
    context: Optional[ChatContext] = None
    history: list[ChatMessage] = Field(default_factory=list, max_length=20)


class ChatResponse(BaseModel):
    reply: str
    mode: str


def _get_user_stats_summary(db: Session, user_id: Optional[int], user_name: str) -> dict[str, Any]:
    """Compile high-level stats for context personalization."""
    if not user_id:
        return {"name": "Learner", "total_assessments": 0, "average_score": None, "favorite_topic": "General"}

    try:
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

        percentages = [
            (a.score / a.total_questions * 100)
            for a in completed
            if a.total_questions > 0
        ]
        avg_score = round(sum(percentages) / len(percentages), 1) if percentages else None

        topic_counts: dict[str, int] = {}
        for _, topic in rows:
            if topic:
                topic_counts[topic] = topic_counts.get(topic, 0) + 1
        favorite_topic = max(topic_counts, key=topic_counts.get) if topic_counts else "General Knowledge"

        return {
            "name": user_name or "Learner",
            "total_assessments": total,
            "completed_assessments": completed_count,
            "average_score": avg_score,
            "favorite_topic": favorite_topic,
        }
    except Exception as exc:
        logger.warning("Could not compile user stats for chat context: %s", exc)
        return {"name": user_name or "Learner", "total_assessments": 0, "average_score": None, "favorite_topic": "General"}


@router.post("/message", response_model=ChatResponse)
async def send_chat_message(
    chat_request: ChatRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Generate a conversational response from Loomie AI Tutor."""
    user = request.session.get("user")
    user_id = int(user["user_id"]) if user and user.get("user_id") else None
    user_name = user.get("name") if user else "Learner"

    user_stats = _get_user_stats_summary(db, user_id, user_name)

    # Reconstruct message history
    messages = [{"role": msg.role, "content": msg.content} for msg in chat_request.history]
    messages.append({"role": "user", "content": chat_request.message})

    context_dict = chat_request.context.model_dump() if chat_request.context else {}

    try:
        reply = await ChatService.generate_response(
            messages=messages,
            mode=chat_request.mode,
            context=context_dict,
            user_stats=user_stats,
        )
        return ChatResponse(reply=reply, mode=chat_request.mode)

    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=str(val_err))
    except Exception as exc:
        logger.exception("Chat generation failed: %s", exc)
        raise HTTPException(
            status_code=502,
            detail="Loomie is temporarily unavailable. Please try again shortly.",
        ) from exc


@router.post("/stream")
async def stream_chat_message(
    chat_request: ChatRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Stream Loomie AI Tutor response as Server-Sent Events (SSE)."""
    user = request.session.get("user")
    user_id = int(user["user_id"]) if user and user.get("user_id") else None
    user_name = user.get("name") if user else "Learner"

    user_stats = _get_user_stats_summary(db, user_id, user_name)

    messages = [{"role": msg.role, "content": msg.content} for msg in chat_request.history]
    messages.append({"role": "user", "content": chat_request.message})

    context_dict = chat_request.context.model_dump() if chat_request.context else {}

    async def event_generator():
        try:
            async for token in ChatService.stream_response(
                messages=messages,
                mode=chat_request.mode,
                context=context_dict,
                user_stats=user_stats,
            ):
                payload = json.dumps({"delta": token})
                yield f"data: {payload}\n\n"
            yield "data: [DONE]\n\n"
        except ValueError as val_err:
            payload = json.dumps({"error": str(val_err)})
            yield f"data: {payload}\n\n"
        except Exception as exc:
            logger.exception("Error in chat streaming: %s", exc)
            payload = json.dumps({"error": "Streaming encountered an error."})
            yield f"data: {payload}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
