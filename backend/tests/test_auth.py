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


def test_unauthenticated_profile_returns_401():
    """Unauthenticated GET /auth/me returns 401."""
    response = client.get("/auth/me")
    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


def test_authenticated_profile_returns_user():
    """Authenticated GET /auth/me returns the user profile."""
    cookie = create_session_cookie({
        "user_id": 1,
        "name": "Chirag Kaura",
        "email": "chiragkaura.work@gmail.com",
        "picture": "https://example.com/avatar.png",
    })

    response = client.get("/auth/me", cookies={"session": cookie})
    assert response.status_code == 200
    data = response.json()
    assert "user" in data
    assert data["user"]["name"] == "Chirag Kaura"
    assert data["user"]["email"] == "chiragkaura.work@gmail.com"


def test_logout_clears_session():
    """POST /auth/logout clears the session cookie."""
    cookie = create_session_cookie({
        "user_id": 1,
        "email": "chiragkaura.work@gmail.com",
    })

    response = client.post("/auth/logout", cookies={"session": cookie})
    assert response.status_code == 200
    assert response.json() == {"message": "Logged out successfully"}
    assert "session=null" in response.headers.get("set-cookie", "")


def test_google_login_redirects_to_google():
    """GET /auth/google/login redirects to Google OAuth consent screen."""
    response = client.get("/auth/google/login")
    assert response.status_code == 302
    location = response.headers.get("location", "")
    assert "https://accounts.google.com/o/oauth2/v2/auth" in location
    assert config.GOOGLE_CLIENT_ID in location
    assert "scope=openid+email+profile" in location


def test_unauthenticated_quiz_generate_returns_401():
    """Unauthenticated POST /quiz/generate returns 401."""
    response = client.post(
        "/quiz/generate",
        json={"topic": "Python Programming", "difficulty": "Easy"},
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Please sign in to continue."}


def test_unauthenticated_quiz_submit_returns_401():
    """Unauthenticated POST /quiz/submit returns 401."""
    response = client.post(
        "/quiz/submit",
        json={"quiz_id": 1, "selected_answers": ["A", "B", "C", "D", "A"]},
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Please sign in to continue."}


@patch("backend.app.api.routes.generate_questions")
def test_authenticated_quiz_lifecycle(mock_generate):
    """Authenticated user can generate a quiz and submit answers."""
    mock_questions = [
        Question(
            question=f"Test Question {i}",
            options=["Option A", "Option B", "Option C", "Option D"],
            correct_answer="Option A",
            explanation="Option A is correct.",
        )
        for i in range(1, 6)
    ]
    mock_generate.return_value = mock_questions

    cookie = create_session_cookie({
        "user_id": 1,
        "name": "Dev User",
        "email": "askloom-dev@example.com",
    })

    # 1. Generate quiz with auth cookie
    gen_resp = client.post(
        "/quiz/generate",
        json={"topic": "Python Programming", "difficulty": "Easy"},
        cookies={"session": cookie},
    )
    assert gen_resp.status_code == 200
    gen_data = gen_resp.json()
    assert "quiz_id" in gen_data
    assert len(gen_data["questions"]) == 5
    quiz_id = int(gen_data["quiz_id"])

    # 2. Submit quiz with auth cookie
    sub_resp = client.post(
        "/quiz/submit",
        json={
            "quiz_id": quiz_id,
            "selected_answers": ["Option A", "Option A", "Option A", "Option A", "Option A"],
        },
        cookies={"session": cookie},
    )
    assert sub_resp.status_code == 200
    sub_data = sub_resp.json()
    assert sub_data["quiz_id"] == quiz_id
    assert sub_data["score"] == 5
    assert sub_data["total_questions"] == 5
    assert sub_data["percentage"] == 100.0
