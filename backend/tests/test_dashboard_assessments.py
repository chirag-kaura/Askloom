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


@patch("backend.app.api.routes.generate_questions")
def test_resume_in_progress_quiz(mock_generate):
    """Verify GET /quiz/resume/{id} returns active questions and prohibits cross-user access."""
    mock_questions = [
        Question(
            question=f"Resume Question {i}",
            options=["A", "B", "C", "D"],
            correct_answer="A",
            explanation="Explanation",
        )
        for i in range(1, 6)
    ]
    mock_generate.return_value = mock_questions

    cookie_user1 = create_session_cookie({"user_id": 1, "email": "askloom-dev@example.com"})
    cookie_user2 = create_session_cookie({"user_id": 2, "email": "other@example.com"})

    gen_resp = client.post(
        "/quiz/generate",
        json={"topic": "SQL & Databases", "difficulty": "Easy"},
        cookies={"session": cookie_user1},
    )
    assert gen_resp.status_code == 200
    quiz_id = int(gen_resp.json()["quiz_id"])

    # Owner resumes successfully
    resume_resp = client.get(f"/quiz/resume/{quiz_id}", cookies={"session": cookie_user1})
    assert resume_resp.status_code == 200
    resume_data = resume_resp.json()
    assert resume_data["quiz_id"] == quiz_id
    assert resume_data["topic"] == "SQL & Databases"
    assert len(resume_data["questions"]) == 5
    assert resume_data["alternates_remaining"] == 3
    # Check no correct answer leak
    assert "correct_answer" not in resume_data["questions"][0]
    assert "explanation" not in resume_data["questions"][0]

    # Non-owner gets 403 Forbidden
    forbidden = client.get(f"/quiz/resume/{quiz_id}", cookies={"session": cookie_user2})
    assert forbidden.status_code == 403


@patch("backend.app.api.routes.generate_questions")
def test_alternate_question_flow(mock_generate):
    """Verify POST /quiz/alternate swaps active slot, updates version history, and enforces 3-alternate limit."""
    initial_questions = [
        Question(
            question=f"Initial Q{i}",
            options=["Opt1", "Opt2", "Opt3", "Opt4"],
            correct_answer="Opt1",
            explanation="Initial explanation",
        )
        for i in range(1, 6)
    ]
    alt_question = [
        Question(
            question="Alternate Question 1 Version 2",
            options=["AltA", "AltB", "AltC", "AltD"],
            correct_answer="AltB",
            explanation="Alternate explanation",
        )
    ]
    mock_generate.side_effect = [initial_questions, alt_question, alt_question, alt_question, alt_question]

    cookie = create_session_cookie({"user_id": 1, "email": "askloom-dev@example.com"})

    gen_resp = client.post(
        "/quiz/generate",
        json={"topic": "Python Programming", "difficulty": "Medium"},
        cookies={"session": cookie},
    )
    assert gen_resp.status_code == 200
    quiz_id = int(gen_resp.json()["quiz_id"])

    # 1. Generate 1st alternate for slot 1
    alt_resp = client.post(
        "/quiz/alternate",
        json={"quiz_id": quiz_id, "slot_number": 1},
        cookies={"session": cookie},
    )
    assert alt_resp.status_code == 200
    data = alt_resp.json()
    assert data["slot_number"] == 1
    assert data["version_number"] == 2
    assert data["alternates_remaining"] == 2
    assert data["question"]["question"] == "Alternate Question 1 Version 2"

    # 2. Check resume returns the updated alternate question and remaining count
    res_resp = client.get(f"/quiz/resume/{quiz_id}", cookies={"session": cookie})
    assert res_resp.status_code == 200
    res_data = res_resp.json()
    assert res_data["alternates_remaining"] == 2
    assert res_data["questions"][0]["question"] == "Alternate Question 1 Version 2"
