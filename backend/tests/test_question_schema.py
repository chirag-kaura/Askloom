
import pytest
from pydantic import ValidationError

from backend.app.schemas.question import Question


def test_valid_question():
    question = Question(
        question="What is the capital of France?",
        options=["Paris", "Rome", "Berlin", "Madrid"],
        correct_answer="Paris",
        explanation="Paris is the capital of France.",
    )

    assert question.correct_answer == "Paris"
    assert len(question.options) == 4


def test_question_requires_exactly_four_options():
    with pytest.raises(ValidationError):
        Question(
            question="What is the capital of France?",
            options=["Paris", "Rome", "Berlin"],
            correct_answer="Paris",
            explanation="Paris is the capital of France.",
        )
