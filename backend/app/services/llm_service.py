# Askloom starter file: backend/app/services/llm_service.py


import json
import random
import time

from groq import Groq, RateLimitError
from pydantic import TypeAdapter

from backend.app.core.config import GROQ_API_KEY
from backend.app.schemas.question import Question


if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY is missing. Check your .env file.")

client = Groq(api_key=GROQ_API_KEY)

question_adapter = TypeAdapter(list[Question])

MAX_ATTEMPTS = 3


def generate_questions(
    topic: str,
    difficulty: str = "Medium",
) -> list[Question]:
    """Generate five validated quiz questions using Groq."""

    prompt = f"""
Generate exactly 5 multiple-choice quiz questions.

Topic: {topic}
Difficulty: {difficulty}

Return a JSON object with a single key named "questions".
Its value must be an array containing exactly 5 questions.

Each question must contain:
- question: a non-empty question
- options: exactly 4 distinct answer options
- correct_answer: exactly one option from options
- explanation: a short explanation of the correct answer

Ensure every correct_answer exactly matches one of its options.
Do not include Markdown fences or text outside the JSON object.
"""

    response = None

    for attempt in range(MAX_ATTEMPTS):
        try:
            response = client.chat.completions.create(
                model="openai/gpt-oss-120b",
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You generate accurate educational quiz "
                            "questions. Return only valid JSON with "
                            'a single "questions" array containing '
                            "exactly five question objects."
                        ),
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                temperature=0.3,
            )
            break

        except RateLimitError:
            if attempt == MAX_ATTEMPTS - 1:
                raise

            # Bounded exponential backoff with small random jitter.
            delay = (2 ** (attempt + 1)) + random.uniform(0, 1)
            time.sleep(delay)

    if response is None:
        raise RuntimeError("Groq did not return a response.")

    content = response.choices[0].message.content

    if not content or not content.strip():
        raise ValueError("Groq returned an empty response.")

    # Parse the JSON object and extract its questions array.
    parsed_response = json.loads(content)

    if not isinstance(parsed_response, dict):
        raise TypeError("Groq response must be a JSON object.")

    raw_questions = parsed_response.get("questions")

    if not isinstance(raw_questions, list):
        raise TypeError(
            'Groq response must contain a "questions" array.'
        )

    if len(raw_questions) != 5:
        raise TypeError("Groq must return exactly 5 questions.")

    # Validate question fields and types using the existing schema.
    questions = question_adapter.validate_python(raw_questions)

    # Enforce answer consistency and four distinct options.
    for question in questions:
        if len(question.options) != 4:
            raise TypeError(
                "Each question must have exactly four options."
            )

        if len(set(question.options)) != 4:
            raise TypeError(
                "Each question must have four distinct options."
            )

        if question.correct_answer not in question.options:
            raise TypeError(
                "The correct answer must match one of the options."
            )

    return questions
