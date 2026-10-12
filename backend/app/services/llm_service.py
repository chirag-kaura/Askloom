# Askloom starter file: backend/app/services/llm_service.py

import json

from groq import Groq
from pydantic import TypeAdapter

from backend.app.core.config import GROQ_API_KEY
from backend.app.schemas.question import Question


if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY is missing. Check your .env file.")

client = Groq(api_key=GROQ_API_KEY)

question_adapter = TypeAdapter(list[Question])


def generate_questions(topic: str, difficulty: str = "Medium") -> list[Question]:
    """Generate five validated quiz questions using Groq."""
    prompt = f"""
Generate exactly 5 multiple-choice quiz questions.

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

    if not content:
        raise ValueError("Groq returned an empty response.")

    raw_questions = json.loads(content)
    questions = question_adapter.validate_python(raw_questions)

    if len(questions) != 5:
        raise ValueError("Groq must return exactly 5 questions.")

    for question in questions:
        if question.correct_answer not in question.options:
            raise ValueError("The correct answer must match one of the options.")

        if len(set(question.options)) != 4:
            raise ValueError("Each question must have four distinct options.")

    return questions
