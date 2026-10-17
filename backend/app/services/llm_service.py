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
You are an experienced assessment designer responsible for creating
accurate, fair, and educational multiple-choice assessments.

Topic: {topic}
Difficulty: {difficulty}

Return ONLY a valid JSON array. Each item must contain:
- question: a non-empty question
- options: exactly 4 distinct answer options
- correct_answer: exactly one option from options
- explanation: a short explanation of the correct answer

Do not include Markdown fences or text outside the JSON.
"""

    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
            {
                "role": "system",
                "content": "You generate accurate educational quiz questions as JSON.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
    )

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
