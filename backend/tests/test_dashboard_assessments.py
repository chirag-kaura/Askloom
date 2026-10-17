import base64
import json
from unittest.mock import patch
from fastapi.testclient import TestClient
from itsdangerous import TimestampSigner

from backend.app.core import config
from backend.app.main import app
from backend.app.schemas.question import Question

client = TestClient(app, follow_redirects=False)


def create_session_cookie(user_data: dict) -> str:
    """Create a signed Starlette session cookie for testing."""
    signer = TimestampSigner(config.SESSION_SECRET)
    payload = json.dumps({"user": user_data}).encode("utf-8")
    return signer.sign(base64.b64encode(payload)).decode("utf-8")


def test_unauthenticated_stats_returns_defaults():
    """Unauthenticated GET /quiz/stats returns guest defaults."""
    response = client.get("/quiz/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["authenticated"] is False
    assert data["total_assessments"] == 0
    assert data["completed_assessments"] == 0
    assert data["average_score"] is None


def test_unauthenticated_history_returns_empty():
    """Unauthenticated GET /quiz/history returns empty list."""
    response = client.get("/quiz/history")
    assert response.status_code == 200
    data = response.json()
    assert data["authenticated"] is False
    assert data["assessments"] == []


def test_unauthenticated_review_returns_401():
    """Unauthenticated GET /quiz/review/{id} returns 401."""
    response = client.get("/quiz/review/1")
    assert response.status_code == 401
    assert response.json() == {"detail": "Please sign in to continue."}


@patch("backend.app.api.routes.generate_questions")
def test_dashboard_and_assessments_lifecycle(mock_generate):
    """Authenticated user generates and submits a quiz, then verifies stats, history, and review."""
    mock_questions = [
        Question(
            question=f"Lifecycle Question {i}",
            options=["Alpha", "Beta", "Gamma", "Delta"],
            correct_answer="Alpha",
            explanation="Alpha is always first.",
        )
        for i in range(1, 6)
    ]
    mock_generate.return_value = mock_questions

    cookie = create_session_cookie({
        "user_id": 1,
        "name": "Dev User",
        "email": "askloom-dev@example.com",
    })

    # 1. Generate quiz
    gen_resp = client.post(
        "/quiz/generate",
        json={"topic": "Python Programming", "difficulty": "Medium"},
        cookies={"session": cookie},
    )
    assert gen_resp.status_code == 200
    quiz_id = int(gen_resp.json()["quiz_id"])

    # 2. Check stats while in_progress
    stats_resp = client.get("/quiz/stats", cookies={"session": cookie})
    assert stats_resp.status_code == 200
    stats_data = stats_resp.json()
    assert stats_data["authenticated"] is True
    assert stats_data["total_assessments"] >= 1

    # 3. Check history contains this quiz
    hist_resp = client.get("/quiz/history", cookies={"session": cookie})
    assert hist_resp.status_code == 200
    hist_data = hist_resp.json()
    assert hist_data["authenticated"] is True
    quiz_entry = next((q for q in hist_data["assessments"] if q["assessment_id"] == quiz_id), None)
    assert quiz_entry is not None
    assert quiz_entry["status"] == "in_progress"

    # 4. Submit answers
    sub_resp = client.post(
        "/quiz/submit",
        json={
            "quiz_id": quiz_id,
            "selected_answers": ["Alpha", "Alpha", "Beta", "Alpha", "Alpha"],
        },
        cookies={"session": cookie},
    )
    assert sub_resp.status_code == 200
    assert sub_resp.json()["score"] == 4

    # 5. Review the past completed quiz
    rev_resp = client.get(f"/quiz/review/{quiz_id}", cookies={"session": cookie})
    assert rev_resp.status_code == 200
    rev_data = rev_resp.json()
    assert rev_data["quiz_id"] == quiz_id
    assert rev_data["score"] == 4
    assert rev_data["status"] == "completed"
    assert len(rev_data["questions"]) == 5
    assert rev_data["questions"][0]["question"] == "Lifecycle Question 1"

    # 6. Verify unauthorized user cannot review someone else's quiz
    other_user_cookie = create_session_cookie({
        "user_id": 99999,
        "email": "intruder@example.com",
    })
    forbidden_resp = client.get(f"/quiz/review/{quiz_id}", cookies={"session": other_user_cookie})
    assert forbidden_resp.status_code == 403
