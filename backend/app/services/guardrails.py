# backend/app/services/guardrails.py

import re
from fastapi import HTTPException
from backend.app.schemas.question import Question

# Known prompt injection and system override patterns
INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions|prompts|directions)",
    r"(reveal|show|print|leak|output)\s+(the\s+)?(system\s+prompt|developer\s+mode|instructions)",
    r"you\s+are\s+now\s+(a|an)?\s*(dan|developer|jailbroken|unrestricted|god)",
    r"dan\s+mode|jailbreak|bypass\s+filter|override\s+safety",
    r"<script[\s\S]*?>[\s\S]*?<\/script>",
    r"javascript:\s*",
    r"(\bunion\b\s+\bselect\b|\bdrop\b\s+\btable\b|\binsert\b\s+\binto\b)",
    r"exec\s*\(|eval\s*\(|import\s+os|system\s*\(",
    r"pretend\s+(you\s+are|to\s+be)",
    r"act\s+as\s+an?\s+unfiltered",
]

# Sensitive, unsafe, or harmful topics disallowed in educational assessments
PROHIBITED_THEMES = [
    r"\b(bomb|weapon|explosive|bioweapon|poison|meth|heroin|fentanyl)\b",
    r"\b(hack\s+into|ddos\s+attack|exploit\s+vulnerability|ransomware\s+creation)\b",
    r"\b(hate\s+speech|slur|genocide|nazi)\b",
    r"\b(suicide|self-harm|torture)\b",
]

DISALLOWED_OPTION_PATTERNS = [
    r"^all\s+of\s+the\s+above$",
    r"^none\s+of\s+the\s+above$",
    r"^both\s+[a-d]\s+and\s+[a-d]$",
]


def validate_topic_guardrails(topic: str) -> str:
    """
    Validate and sanitize user-submitted assessment topic.
    Guards against prompt injections, off-topic abuse, and harmful inputs.
    """
    if not topic or not isinstance(topic, str):
        raise HTTPException(
            status_code=400,
            detail="Topic cannot be empty.",
        )

    clean_topic = topic.strip()

    # 1. Length guardrail
    if len(clean_topic) < 2:
        raise HTTPException(
            status_code=400,
            detail="Topic is too short. Please provide a descriptive subject name (at least 2 characters).",
        )

    if len(clean_topic) > 100:
        raise HTTPException(
            status_code=400,
            detail="Topic exceeds the maximum allowed length of 100 characters.",
        )

    # 2. Minimum educational content (must contain letters, not just symbols or numbers)
    letters = re.findall(r"[A-Za-z]", clean_topic)
    if len(letters) < 2:
        raise HTTPException(
            status_code=400,
            detail="Topic must contain recognizable subject words.",
        )

    # 3. Prompt injection guardrail
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, clean_topic, re.IGNORECASE):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Invalid topic detected. Assessment topics must be legitimate "
                    "educational or technical subjects and must not contain prompt instructions."
                ),
            )

    # 4. Prohibited themes guardrail
    for pattern in PROHIBITED_THEMES:
        if re.search(pattern, clean_topic, re.IGNORECASE):
            raise HTTPException(
                status_code=400,
                detail="This topic falls outside of Askloom's educational policy.",
            )

    # Sanitize multiple consecutive whitespaces
    sanitized = re.sub(r"\s+", " ", clean_topic)
    return sanitized


def validate_question_grounding(questions: list[Question], topic: str) -> list[Question]:
    """
    Verify structural and defensibility grounding of generated questions.
    Ensures:
      - Exactly 5 questions
      - Exactly 4 non-empty, distinct options per question
      - Correct answer matches an option verbatim
      - No trivial cop-out options ('All of the above', 'None of the above')
      - Non-empty, defensible explanation
    """
    if not isinstance(questions, list) or len(questions) != 5:
        raise ValueError(
            f"Grounding error: Expected exactly 5 questions, received {len(questions) if isinstance(questions, list) else 0}."
        )

    for idx, q in enumerate(questions, start=1):
        # 1. Question text
        if not q.question or not q.question.strip():
            raise ValueError(f"Grounding error: Question {idx} text is empty.")

        # 2. Options validation
        if not isinstance(q.options, list) or len(q.options) != 4:
            raise ValueError(f"Grounding error: Question {idx} must have exactly 4 options.")

        cleaned_options = [opt.strip() for opt in q.options if isinstance(opt, str) and opt.strip()]
        if len(cleaned_options) != 4:
            raise ValueError(f"Grounding error: Question {idx} contains empty options.")

        # Check distinctness
        if len(set(cleaned_options)) != 4:
            raise ValueError(f"Grounding error: Question {idx} has duplicate options.")

        # Check for disallowed shortcuts (e.g. All of the above)
        for opt in cleaned_options:
            for dis_pat in DISALLOWED_OPTION_PATTERNS:
                if re.match(dis_pat, opt, re.IGNORECASE):
                    raise ValueError(
                        f"Grounding error: Question {idx} uses disallowed trivial option '{opt}'."
                    )

        # 3. Correct answer match
        if q.correct_answer.strip() not in cleaned_options:
            raise ValueError(
                f"Grounding error: Correct answer for Question {idx} ('{q.correct_answer}') does not match any of the 4 options."
            )

        # 4. Explanation check
        if not q.explanation or not q.explanation.strip():
            raise ValueError(f"Grounding error: Question {idx} must include an educational explanation.")

    return questions
