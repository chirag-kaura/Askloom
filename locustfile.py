
from locust import HttpUser, task, between


class AskloomUser(HttpUser):
    # Wait 1–3 seconds between tasks, simulating user behavior.
    wait_time = between(1, 3)

    @task
    def check_health(self):
        with self.client.get(
            "/health",
            name="GET /health",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(
                    f"Health check failed: HTTP {response.status_code}"
                )

    @task(3)
    def generate_quiz(self):
        payload = {
            "topic": "Python programming",
            "difficulty": "Easy",
        }

        with self.client.post(
            "/quiz/generate",
            json=payload,
            name="POST /quiz/generate",
            catch_response=True,
            timeout=30,
        ) as response:
            if response.status_code != 200:
                response.failure(
                    f"Quiz generation failed: HTTP {response.status_code}"
                )
                return

            try:
                data = response.json()
                questions = data.get("questions", [])

                if len(questions) != 5:
                    response.failure(
                        f"Expected 5 questions, received {len(questions)}"
                    )
            except (ValueError, AttributeError):
                response.failure("Invalid JSON response")
