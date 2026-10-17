import base64
import json
import random
from itsdangerous import TimestampSigner
from locust import HttpUser, task, between

from backend.app.core.config import SESSION_SECRET

TOPICS = [
    "Python Programming",
    "SQL & Databases",
    "Data Science & Machine Learning",
    "Generative AI & LLMs",
    "Statistics & Probability",
    "Docker & Containers",
    "Cloud Architecture",
]

DIFFICULTIES = ["Easy", "Medium", "Hard"]


VALID_USER_IDS = [1, 2, 3]


def generate_test_cookie(user_id: int) -> str:
    """Generate a valid signed Starlette session cookie for virtual test users."""
    secret = SESSION_SECRET or "dev-insecure-secret-key-change-in-prod"
    signer = TimestampSigner(secret)
    user_data = {
        "user_id": user_id,
        "name": f"LoadTester {user_id}",
        "email": f"loadtester_{user_id}@example.com",
    }
    payload = json.dumps({"user": user_data}).encode("utf-8")
    return signer.sign(base64.b64encode(payload)).decode("utf-8")


class AskloomLoadTester(HttpUser):
    # Simulated think time between user actions (0.5 to 2.0s)
    wait_time = between(0.5, 2.0)

    def on_start(self):
        """Initialize authenticated virtual user session on startup."""
        self.user_id = random.choice(VALID_USER_IDS)
        self.cookie_value = generate_test_cookie(self.user_id)
        self.client.cookies.set("session", self.cookie_value)
        self.active_quiz_id = None
        self.completed_quiz_id = None

    @task(4)
    def browse_dashboard_and_stats(self):
        """Simulate user browsing Dashboard, metrics, and history."""
        # 1. Health check
        with self.client.get(
            "/health",
            name="GET /health",
            catch_response=True,
        ) as res:
            if res.status_code != 200:
                res.failure(f"Health check failed: {res.status_code}")

        # 2. Stats endpoint
        with self.client.get(
            "/quiz/stats",
            name="GET /quiz/stats",
            catch_response=True,
        ) as res:
            if res.status_code != 200:
                res.failure(f"Stats fetch failed: {res.status_code}")

        # 3. Assessment history
        with self.client.get(
            "/quiz/history",
            name="GET /quiz/history",
            catch_response=True,
        ) as res:
            if res.status_code != 200:
                res.failure(f"History fetch failed: {res.status_code}")

    @task(3)
    def generate_assessment(self):
        """Simulate creating a new assessment."""
        topic = random.choice(TOPICS)
        difficulty = random.choice(DIFFICULTIES)

        with self.client.post(
            "/quiz/generate",
            json={"topic": topic, "difficulty": difficulty},
            name="POST /quiz/generate",
            catch_response=True,
            timeout=30,
        ) as res:
            if res.status_code != 200:
                res.failure(f"Quiz generation failed: HTTP {res.status_code} - {res.text[:120]}")
                return

            try:
                data = res.json()
                questions = data.get("questions", [])
                quiz_id = data.get("quiz_id")

                if len(questions) != 5:
                    res.failure(f"Expected 5 questions, got {len(questions)}")
                    return

                if not quiz_id:
                    res.failure("Missing quiz_id in response")
                    return

                self.active_quiz_id = quiz_id
            except Exception as e:
                res.failure(f"Invalid JSON: {e}")

    @task(2)
    def submit_assessment_answers(self):
        """Simulate answering and submitting a quiz."""
        if not self.active_quiz_id:
            return

        # Submit answers
        sample_answers = ["A", "B", "C", "D", "A"]
        with self.client.post(
            "/quiz/submit",
            json={
                "quiz_id": int(self.active_quiz_id),
                "selected_answers": sample_answers,
            },
            name="POST /quiz/submit",
            catch_response=True,
            timeout=15,
        ) as res:
            if res.status_code in (200, 409):
                # 200 is successful submit; 409 means already submitted (acceptable under concurrency)
                self.completed_quiz_id = self.active_quiz_id
                self.active_quiz_id = None
            else:
                res.failure(f"Submit failed: HTTP {res.status_code} - {res.text[:120]}")

    @task(1)
    def review_completed_assessment(self):
        """Simulate reviewing a completed assessment with explanations."""
        if not self.completed_quiz_id:
            return

        with self.client.get(
            f"/quiz/review/{self.completed_quiz_id}",
            name="GET /quiz/review/[id]",
            catch_response=True,
            timeout=15,
        ) as res:
            if res.status_code != 200:
                res.failure(f"Review fetch failed: HTTP {res.status_code} - {res.text[:120]}")
