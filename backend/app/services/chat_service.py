# Askloom: backend/app/services/chat_service.py

import asyncio
import logging
import re
from collections.abc import AsyncGenerator
from typing import Any, Optional

from groq import AsyncGroq, RateLimitError

from backend.app.core.config import GROQ_API_KEY
from backend.app.services.guardrails import validate_topic_guardrails

logger = logging.getLogger(__name__)

if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY is missing. Check your .env file.")

async_client = AsyncGroq(api_key=GROQ_API_KEY)
_chat_semaphore = asyncio.Semaphore(5)

PRIMARY_MODEL = "openai/gpt-oss-120b"
FALLBACK_MODEL = "openai/gpt-oss-20b"

SOCRATIC_HINT_SYSTEM_PROMPT = """You are Loomie, Askloom's expert AI Learning Coach.
The student is currently taking an assessment and has asked for guidance or a hint on a question.

STRICT SOCRATIC GUARDRAILS:
1. NEVER reveal, hint at, or confirm which option (A, B, C, or D) or text is the correct answer.
2. Under no circumstances say phrases like "The answer is...", "Choose option...", or "Option X is correct".
3. Guide the student Socratically:
   - Identify the fundamental concept or rule being tested.
   - Ask a thought-provoking guiding question to help them reason it out.
   - If code is involved, prompt them to trace variable state or evaluation order at the key line.
   - Use an intuitive real-world analogy if helpful.
4. Keep your hint brief, encouraging, and clear (max 2-4 sentences, strictly under 100 words).
5. FORMATTING: NEVER use markdown tables. Format code using markdown backticks (`code`). Complete thoughts cleanly without trailing off."""

DEEP_DIVE_REVIEW_SYSTEM_PROMPT = """You are Loomie, Askloom's expert AI Learning Coach.
The student has completed an assessment and wants to deeply understand this specific question and its answers.

PEDAGOGICAL REVIEW RULES:
1. Clearly explain WHY the correct answer is right and WHY the student's selected choice (if incorrect) was a common misconception or flawed.
2. Provide a minimal, crystal-clear code snippet or concrete example illustrating the difference.
3. Highlight practical, real-world implications or industry best practices related to this concept.
4. FORMATTING: Keep explanation concise, structured, and easy to digest (strictly under 180 words).
   - Use clean GitHub-flavored markdown: short bullet points, bold keywords, and concise code blocks with language tags.
   - NEVER use markdown tables (| col |). They break the mobile and drawer layout.
5. Maintain an empowering, supportive, and educational tone. Ensure every sentence and code block is complete."""

TUTOR_GENERAL_SYSTEM_PROMPT = """You are Loomie, Askloom's intelligent AI Learning Coach and technical mentor.
You assist learners with mastering computer science, programming, databases, AI/ML, and system architecture.

ASKLOOM PLATFORM GROUNDING:
- Askloom offers 5 primary assessment topics:
  1. Python Programming
  2. Data Science & Machine Learning
  3. Generative AI & LLMs
  4. SQL & Databases
  5. Statistics & Probability
  (Plus custom subjects like Docker, Cloud Architecture, etc. via "Others")
- Assessment difficulty levels: Easy, Medium, Hard.
- When recommending practice or next steps based on the student's profile or query:
  - ALWAYS recommend taking a specific assessment directly on Askloom (specifying the Topic and Difficulty level).
  - STRICTLY FORBIDDEN: NEVER mention or link to external learning sites or platforms (e.g., NO W3Schools, LeetCode, HackerRank, Coursera, Udemy, etc.). All practice must happen on Askloom.

STRICT CONCISENESS & FORMATTING RULES:
1. Keep your entire response concise, conversational, and punchy (2 to 3 short paragraphs or a brief bulleted list, STRICTLY UNDER 150 words total).
2. NO MARKDOWN TABLES: Never generate markdown tables (| col1 | col2 |). The chat drawer is narrow (440px) and tables break the UI. Use simple bullet points or numbered lists instead.
3. If student performance statistics are provided, deliver a quick 1-sentence diagnostic followed by clear, actionable Askloom assessment recommendations.
4. Always conclude thoughts and sentences cleanly within the word budget. Never leave text cut off or incomplete."""


def _check_chat_injection(message: str) -> None:
    """Detect prompt injection attempts in chat messages."""
    suspicious_patterns = [
        r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions",
        r"disregard\s+(all\s+)?(previous|prior|above)",
        r"you\s+are\s+now\s+(an?|in)\s+dan\s+mode",
        r"system\s*prompt",
        r"jailbreak",
        r"reveal\s+(your\s+)?(system|internal)\s+(prompt|instructions)",
    ]
    for pattern in suspicious_patterns:
        if re.search(pattern, message, re.IGNORECASE):
            raise ValueError("Prompt injection or system override detected.")


def build_system_message(
    mode: str,
    context: Optional[dict[str, Any]] = None,
    user_stats: Optional[dict[str, Any]] = None,
) -> str:
    """Build the contextualized system prompt based on mode and active session context."""
    context = context or {}
    user_stats = user_stats or {}

    if mode == "socratic_hint":
        prompt = SOCRATIC_HINT_SYSTEM_PROMPT
        question_text = context.get("question_text", "")
        options = context.get("options", [])
        topic = context.get("topic", "General Knowledge")
        difficulty = context.get("difficulty", "Medium")

        prompt += f"\n\nCURRENT QUIZ CONTEXT:\n- Topic: {topic}\n- Difficulty: {difficulty}\n- Question: {question_text}"
        if options:
            prompt += f"\n- Options presented to student: {', '.join(options)}"
        prompt += "\nREMEMBER: Guide Socratically. DO NOT REVEAL THE CORRECT OPTION OR ELIMINATE OPTIONS."
        return prompt

    elif mode == "deep_dive_review":
        prompt = DEEP_DIVE_REVIEW_SYSTEM_PROMPT
        question_text = context.get("question_text", "")
        selected_answer = context.get("selected_answer", "None")
        correct_answer = context.get("correct_answer", "")
        explanation = context.get("explanation", "")
        topic = context.get("topic", "")

        prompt += f"\n\nREVIEW CONTEXT:"
        if topic:
            prompt += f"\n- Topic: {topic}"
        prompt += f"\n- Question: {question_text}"
        prompt += f"\n- Student's Choice: {selected_answer}"
        if correct_answer:
            prompt += f"\n- Correct Answer: {correct_answer}"
        if explanation:
            prompt += f"\n- Official Explanation: {explanation}"
        return prompt

    else:  # tutor_general
        prompt = TUTOR_GENERAL_SYSTEM_PROMPT
        if user_stats:
            user_name = user_stats.get("name", "Student")
            total = user_stats.get("total_assessments", 0)
            avg = user_stats.get("average_score", None)
            topic = user_stats.get("favorite_topic", "None")
            prompt += f"\n\nSTUDENT PROFILE:\n- Name: {user_name}\n- Total Assessments: {total}\n- Average Score: {avg if avg is not None else 'N/A'}%\n- Top Subject: {topic}"
        return prompt


class ChatService:
    """Orchestrates conversations with Loomie AI Tutor."""

    @staticmethod
    async def generate_response(
        messages: list[dict[str, str]],
        mode: str = "tutor_general",
        context: Optional[dict[str, Any]] = None,
        user_stats: Optional[dict[str, Any]] = None,
    ) -> str:
        """Generate a complete chat response asynchronously."""
        # 1. Guardrail check on the latest user message
        if messages and messages[-1].get("role") == "user":
            _check_chat_injection(messages[-1]["content"])

        system_prompt = build_system_message(mode, context, user_stats)

        groq_messages = [{"role": "system", "content": system_prompt}]
        # Keep last 6 conversation turns for coherent context
        groq_messages.extend(messages[-6:])

        async with _chat_semaphore:
            try:
                response = await async_client.chat.completions.create(
                    model=PRIMARY_MODEL,
                    messages=groq_messages,
                    temperature=0.4,
                    max_tokens=800,
                )
                return response.choices[0].message.content or ""
            except Exception as e:
                logger.warning("Primary model failed in ChatService, attempting fallback: %s", e)
                response = await async_client.chat.completions.create(
                    model=FALLBACK_MODEL,
                    messages=groq_messages,
                    temperature=0.4,
                    max_tokens=800,
                )
                return response.choices[0].message.content or ""

    @staticmethod
    async def stream_response(
        messages: list[dict[str, str]],
        mode: str = "tutor_general",
        context: Optional[dict[str, Any]] = None,
        user_stats: Optional[dict[str, Any]] = None,
    ) -> AsyncGenerator[str, None]:
        """Stream chat tokens token-by-token."""
        if messages and messages[-1].get("role") == "user":
            _check_chat_injection(messages[-1]["content"])

        system_prompt = build_system_message(mode, context, user_stats)

        groq_messages = [{"role": "system", "content": system_prompt}]
        groq_messages.extend(messages[-6:])

        async with _chat_semaphore:
            try:
                stream = await async_client.chat.completions.create(
                    model=PRIMARY_MODEL,
                    messages=groq_messages,
                    temperature=0.4,
                    max_tokens=800,
                    stream=True,
                )
                async for chunk in stream:
                    delta = chunk.choices[0].delta.content
                    if delta:
                        yield delta
            except Exception as e:
                logger.warning("Primary stream failed in ChatService, attempting fallback: %s", e)
                fallback_stream = await async_client.chat.completions.create(
                    model=FALLBACK_MODEL,
                    messages=groq_messages,
                    temperature=0.4,
                    max_tokens=800,
                    stream=True,
                )
                async for chunk in fallback_stream:
                    delta = chunk.choices[0].delta.content
                    if delta:
                        yield delta
