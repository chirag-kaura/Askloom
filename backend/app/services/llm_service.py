# Askloom starter file: backend/app/services/llm_service.py

import asyncio
import json
import random
import time
from typing import Optional

from groq import AsyncGroq, Groq, RateLimitError
from pydantic import TypeAdapter

from backend.app.core.config import GROQ_API_KEY
from backend.app.schemas.question import Question
from backend.app.services.guardrails import validate_question_grounding

if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY is missing. Check your .env file.")

sync_client = Groq(api_key=GROQ_API_KEY)
async_client = AsyncGroq(api_key=GROQ_API_KEY)

# Concurrency throttling for outbound Groq API requests (prevents 429 burst errors)
_groq_semaphore = asyncio.Semaphore(5)

question_adapter = TypeAdapter(list[Question])

MAX_ATTEMPTS = 3


# ==========================================
# In-Memory Question Cache with TTL
# ==========================================

class QuestionCache:
    """Thread-safe in-memory cache for generated quiz questions."""

    def __init__(self, ttl_seconds: int = 3600):
        self.ttl = ttl_seconds
        self._cache: dict[tuple[str, str], tuple[float, list[Question]]] = {}

    def get(self, topic: str, difficulty: str) -> Optional[list[Question]]:
        key = (topic.strip().lower(), difficulty.strip().lower())
        entry = self._cache.get(key)
        if not entry:
            return None
        cached_time, questions = entry
        if time.time() - cached_time > self.ttl:
            del self._cache[key]
            return None
        # Return copies of models so callers cannot mutate cached state
        return [q.model_copy() for q in questions]

    def set(self, topic: str, difficulty: str, questions: list[Question]):
        key = (topic.strip().lower(), difficulty.strip().lower())
        self._cache[key] = (time.time(), [q.model_copy() for q in questions])

    def clear(self):
        self._cache.clear()


question_cache = QuestionCache(ttl_seconds=86400)

# Pre-seed standard subject pools for lightning-fast sub-15ms response times and zero rate-limit spikes
_SEEDED_POOLS = {
    ("python programming", "medium"): [
        Question(
            question="What is the time complexity of looking up a key in a standard Python dictionary on average?",
            options=["O(1)", "O(log n)", "O(n)", "O(n log n)"],
            correct_answer="O(1)",
            explanation="Python dictionaries use hash tables, providing average-case O(1) time complexity for key lookups.",
        ),
        Question(
            question="Which Python keyword is used to create a generator function that produces values lazily?",
            options=["yield", "return", "generate", "async"],
            correct_answer="yield",
            explanation="The 'yield' keyword turns a standard function into a generator that yields values on demand.",
        ),
        Question(
            question="What does the Global Interpreter Lock (GIL) primarily do in CPython?",
            options=[
                "Prevents multiple native threads from executing Python bytecodes simultaneously",
                "Encrypts sensitive memory variables in memory",
                "Limits recursion depth to prevent stack overflow",
                "Manages garbage collection for cyclical references",
            ],
            correct_answer="Prevents multiple native threads from executing Python bytecodes simultaneously",
            explanation="The GIL ensures thread safety by permitting only one native thread to execute Python bytecode at a time in CPython.",
        ),
        Question(
            question="In Python, which built-in function returns an iterator of tuples containing elements from each iterable?",
            options=["zip()", "map()", "filter()", "enumerate()"],
            correct_answer="zip()",
            explanation="'zip(*iterables)' pairs corresponding elements from multiple iterables into tuples until the shortest iterable is exhausted.",
        ),
        Question(
            question="Which dunder method must a class implement to be used as a context manager with the 'with' statement?",
            options=["__enter__ and __exit__", "__init__ and __del__", "__open__ and __close__", "__iter__ and __next__"],
            correct_answer="__enter__ and __exit__",
            explanation="The context management protocol requires '__enter__' and '__exit__' to set up and tear down resources.",
        ),
    ],
    ("sql & databases", "medium"): [
        Question(
            question="Which SQL constraint guarantees that all values in a column are distinct and cannot be NULL?",
            options=["PRIMARY KEY", "FOREIGN KEY", "UNIQUE", "CHECK"],
            correct_answer="PRIMARY KEY",
            explanation="A PRIMARY KEY uniquely identifies each row in a table and inherently forbids NULL values.",
        ),
        Question(
            question="What type of JOIN returns all records from the left table and matched records from the right table?",
            options=["LEFT OUTER JOIN", "INNER JOIN", "CROSS JOIN", "FULL OUTER JOIN"],
            correct_answer="LEFT OUTER JOIN",
            explanation="LEFT OUTER JOIN keeps all rows from the left table, filling unmatched right columns with NULL.",
        ),
        Question(
            question="In database transactions, which ACID property ensures transactions are committed permanently even in case of power failure?",
            options=["Durability", "Atomicity", "Consistency", "Isolation"],
            correct_answer="Durability",
            explanation="Durability guarantees that once a transaction has committed, its changes survive system crashes or restarts.",
        ),
        Question(
            question="Which clause is used to filter aggregated results generated by a GROUP BY clause in SQL?",
            options=["HAVING", "WHERE", "FILTER", "LIMIT"],
            correct_answer="HAVING",
            explanation="The HAVING clause applies filtering conditions to groups and aggregate functions, whereas WHERE filters individual rows prior to grouping.",
        ),
        Question(
            question="What is the purpose of database indexing on frequently queried columns?",
            options=[
                "Accelerates data retrieval speed at the cost of additional storage and write overhead",
                "Compresses table rows to save disk space",
                "Automatically normalizes database tables to 3NF",
                "Enforces foreign key referential integrity rules",
            ],
            correct_answer="Accelerates data retrieval speed at the cost of additional storage and write overhead",
            explanation="Indexes build search trees or hash maps to rapidly locate rows without full table scans.",
        ),
    ],
    ("generative ai & llms", "medium"): [
        Question(
            question="Which core mechanism allows Transformer models to assign variable attention weights to different tokens across a sequence?",
            options=["Self-Attention", "Recurrent Backpropagation", "Max Pooling", "Convolutional Stride"],
            correct_answer="Self-Attention",
            explanation="Self-attention computes dynamic attention weights between all token pairs in a sequence.",
        ),
        Question(
            question="What is the primary role of Retrieval-Augmented Generation (RAG) in LLM applications?",
            options=[
                "Grounding LLM responses in external, up-to-date domain documents to reduce hallucination",
                "Fine-tuning model weights with reinforcement learning",
                "Increasing token context length via model pruning",
                "Compressing neural weights to 4-bit precision",
            ],
            correct_answer="Grounding LLM responses in external, up-to-date domain documents to reduce hallucination",
            explanation="RAG retrieves relevant external context at inference time and injects it into the prompt, grounding the generation.",
        ),
        Question(
            question="In LLM decoding, what does the 'temperature' parameter directly control?",
            options=[
                "The randomness and diversity of next-token probability distribution",
                "The GPU operating clock speed and heat output",
                "The maximum number of generated output tokens",
                "The frequency of repetition penalties",
            ],
            correct_answer="The randomness and diversity of next-token probability distribution",
            explanation="Higher temperature flattens token logits leading to more creative/diverse tokens, while lower temperature sharpens probabilities toward the most likely token.",
        ),
        Question(
            question="What vector representation technique converts text into dense numerical embeddings for semantic search?",
            options=["Embedding Models", "One-Hot Encoding", "Bag of Words", "Byte-Pair Encoding"],
            correct_answer="Embedding Models",
            explanation="Embedding models map semantic relationships into high-dimensional dense vector spaces.",
        ),
        Question(
            question="What alignment technique uses human preference rankings to steer LLM generation toward safer and more helpful responses?",
            options=["RLHF (Reinforcement Learning from Human Feedback)", "LoRA (Low-Rank Adaptation)", "Quantization", "Gradient Accumulation"],
            correct_answer="RLHF (Reinforcement Learning from Human Feedback)",
            explanation="RLHF trains a reward model on human comparisons to guide policy optimization via PPO or DPO.",
        ),
    ],
    ("data science & machine learning", "medium"): [
        Question(
            question="What does high variance combined with low training error typically indicate in a machine learning model?",
            options=["Overfitting to training data", "Underfitting to training data", "Excessive regularization penalty", "High dataset bias"],
            correct_answer="Overfitting to training data",
            explanation="High variance and low training error signify overfitting, where the model memorizes training noise rather than general patterns.",
        ),
        Question(
            question="Which evaluation metric is most informative when evaluating a binary classifier on a heavily imbalanced dataset?",
            options=["Precision-Recall AUC (PR-AUC)", "Raw Accuracy", "Mean Squared Error", "Adjusted R-squared"],
            correct_answer="Precision-Recall AUC (PR-AUC)",
            explanation="PR-AUC evaluates performance specifically on the minority positive class without distortion from large true negative volumes.",
        ),
        Question(
            question="What unsupervised technique projects high-dimensional data onto orthogonal axes that maximize captured variance?",
            options=["Principal Component Analysis (PCA)", "K-Means Clustering", "Linear Discriminant Analysis", "DBSCAN"],
            correct_answer="Principal Component Analysis (PCA)",
            explanation="PCA computes orthogonal principal components through eigendecomposition or SVD to maximize variance along new axes.",
        ),
        Question(
            question="What distinct effect does L1 (Lasso) regularization have on model weights compared to L2 (Ridge)?",
            options=[
                "It drives insignificant feature coefficients strictly to zero, performing automatic feature selection",
                "It penalizes the square of the weights to shrink all weights proportionally",
                "It scales feature values between 0 and 1",
                "It guarantees convex optimization convergence in fewer iterations",
            ],
            correct_answer="It drives insignificant feature coefficients strictly to zero, performing automatic feature selection",
            explanation="L1 penalty uses absolute value of weights whose sharp geometry forces non-informative weights to become exactly zero.",
        ),
        Question(
            question="Which optimization algorithm dynamically computes individual adaptive learning rates using first and second moment vectors of gradients?",
            options=["Adam (Adaptive Moment Estimation)", "Vanilla Stochastic Gradient Descent", "Batch Gradient Descent", "Perceptron Learning Rule"],
            correct_answer="Adam (Adaptive Moment Estimation)",
            explanation="Adam combines momentum (first moment) with RMSprop (second uncentered moment) for robust adaptive per-parameter step sizes.",
        ),
    ],
    ("statistics & probability", "medium"): [
        Question(
            question="What does the Central Limit Theorem state about the distribution of sample means as sample size grows sufficiently large?",
            options=[
                "The distribution of sample means approaches a normal distribution regardless of the underlying population distribution",
                "The population variance decreases proportionally to the sample size",
                "The sample median becomes strictly equal to the population mode",
                "All extreme outliers are mathematically eliminated",
            ],
            correct_answer="The distribution of sample means approaches a normal distribution regardless of the underlying population distribution",
            explanation="The CLT guarantees asymptotic normality for sums or means of independent identically distributed variables with finite variance.",
        ),
        Question(
            question="In statistical hypothesis testing, what is a Type I error?",
            options=[
                "Rejecting the null hypothesis when it is actually true (false positive)",
                "Failing to reject the null hypothesis when it is false (false negative)",
                "Selecting an inadequate sample size for statistical power",
                "Calculating an incorrect test statistic degrees of freedom",
            ],
            correct_answer="Rejecting the null hypothesis when it is actually true (false positive)",
            explanation="Type I error occurs when a researcher detects a statistically significant effect that does not exist in reality.",
        ),
        Question(
            question="In Bayesian probability, what does the prior probability represent?",
            options=[
                "The initial belief or probability of a hypothesis before taking into account new evidence",
                "The probability of observing the evidence given the hypothesis",
                "The normalized probability of the evidence across all hypotheses",
                "The updated probability of the hypothesis after observing data",
            ],
            correct_answer="The initial belief or probability of a hypothesis before taking into account new evidence",
            explanation="The prior P(H) represents background knowledge before applying Bayes' theorem with likelihood P(E|H) to find the posterior.",
        ),
        Question(
            question="What does a Pearson correlation coefficient of -0.92 indicate between two continuous variables?",
            options=[
                "A strong inverse linear relationship",
                "A weak positive linear relationship",
                "No observable linear correlation",
                "A non-linear quadratic relationship",
            ],
            correct_answer="A strong inverse linear relationship",
            explanation="Values close to -1.0 indicate that as one variable increases, the other variable decreases in a nearly linear fashion.",
        ),
        Question(
            question="What is the precise definition of a p-value in a statistical significance test?",
            options=[
                "The probability of obtaining test results at least as extreme as the observed results, assuming the null hypothesis is true",
                "The probability that the alternative hypothesis is true",
                "The probability that the study results were caused by human calculation error",
                "The probability that the null hypothesis is completely false",
            ],
            correct_answer="The probability of obtaining test results at least as extreme as the observed results, assuming the null hypothesis is true",
            explanation="A p-value measures evidence against the null hypothesis assuming the null hypothesis holds true.",
        ),
    ],
    ("docker & containers", "medium"): [
        Question(
            question="What is the fundamental architectural relationship between a Docker image and a Docker container?",
            options=[
                "A container is a runnable, isolated execution instance of an immutable Docker image",
                "A Docker image is a running instance of a Dockerfile script",
                "Images and containers are identical kernel namespaces",
                "A Docker container compiles image source code on every launch",
            ],
            correct_answer="A container is a runnable, isolated execution instance of an immutable Docker image",
            explanation="Images serve as read-only templates with layered filesystems, while containers add a thin read-write layer and execute them.",
        ),
        Question(
            question="Which Dockerfile instruction sets the fixed command to run when the container starts, and cannot be easily overridden by CLI arguments?",
            options=["ENTRYPOINT", "CMD", "RUN", "EXPOSE"],
            correct_answer="ENTRYPOINT",
            explanation="ENTRYPOINT configures an executable container; arguments supplied to 'docker run' are appended as arguments to ENTRYPOINT.",
        ),
        Question(
            question="What is the primary architectural benefit of utilizing multi-stage Docker builds?",
            options=[
                "Minimizing final production image size by discarding build tools and intermediate files",
                "Allowing containers to run on multiple CPU architectures simultaneously",
                "Enabling automatic container clustering across multiple hosts",
                "Encrypting layer filesystems at rest",
            ],
            correct_answer="Minimizing final production image size by discarding build tools and intermediate files",
            explanation="Multi-stage builds allow developers to use bulky SDKs in build stages and copy only compiled artifacts into a slim final runtime base.",
        ),
        Question(
            question="Where does Docker store managed Named Volumes on the host filesystem by default in Linux?",
            options=["/var/lib/docker/volumes", "/etc/docker/data", "/usr/share/docker/storage", "/tmp/docker-mounts"],
            correct_answer="/var/lib/docker/volumes",
            explanation="Docker manages volume persistence and lifecycle under the '/var/lib/docker/volumes' directory.",
        ),
        Question(
            question="Which Linux kernel feature provides process isolation by restricting what a container process can see (e.g. PID, mount, network)?",
            options=["Namespaces", "Control Groups (cgroups)", "AppArmor", "Chroot Jails"],
            correct_answer="Namespaces",
            explanation="Linux namespaces isolate resources (PID, NET, IPC, MNT, UTS) so container processes believe they own dedicated system resources.",
        ),
    ],
    ("cloud architecture", "medium"): [
        Question(
            question="What architectural capability enables a cloud system to continue operating without interruption despite the failure of one or more components?",
            options=["Fault Tolerance and Redundancy", "Vertical Compute Scaling", "Manual Disaster Recovery", "Monolithic Tight Coupling"],
            correct_answer="Fault Tolerance and Redundancy",
            explanation="Fault tolerance relies on redundant components across availability zones to sustain uptime without service interruption.",
        ),
        Question(
            question="What does horizontal autoscaling (scaling out) perform when cloud system traffic increases?",
            options=[
                "Provisions additional computing instances/nodes to distribute load across a pool",
                "Upgrades CPU and RAM hardware on an existing single server",
                "Compresses incoming network packets to reduce bandwidth",
                "Restarts failing services with higher process priorities",
            ],
            correct_answer="Provisions additional computing instances/nodes to distribute load across a pool",
            explanation="Horizontal scaling adds more instances behind a load balancer rather than increasing the size of a single instance.",
        ),
        Question(
            question="In distributed cloud microservices, why are HTTP PUT and DELETE operations defined as idempotent?",
            options=[
                "Executing the identical request multiple times produces the exact same system state as executing it once",
                "They require mutual TLS authentication tokens",
                "They can only be called through an API gateway",
                "They do not alter database records",
            ],
            correct_answer="Executing the identical request multiple times produces the exact same system state as executing it once",
            explanation="Idempotence guarantees that repeated retries caused by network timeouts do not lead to unintended duplicate side effects.",
        ),
        Question(
            question="Which microservices design pattern detects downstream service failures and prevents cascading system crashes by failing fast?",
            options=["Circuit Breaker Pattern", "Saga Pattern", "CQRS Pattern", "Strangler Fig Pattern"],
            correct_answer="Circuit Breaker Pattern",
            explanation="The Circuit Breaker pattern trips open when downstream failure thresholds are breached, returning fast fallbacks and preventing resource exhaustion.",
        ),
        Question(
            question="Why are stateless services strongly favored in horizontally auto-scaled cloud architectures?",
            options=[
                "Any request can be routed to any healthy instance without requiring sticky sessions or node-specific state",
                "Stateless services do not require network security groups",
                "They eliminate the need for centralized relational databases",
                "They run exclusively in serverless edge functions",
            ],
            correct_answer="Any request can be routed to any healthy instance without requiring sticky sessions or node-specific state",
            explanation="Stateless instances can be spun up or terminated dynamically because persistent state lives in external databases or caches.",
        ),
    ],
}

# Pre-seed cache with standard pools
for (t, d), q_list in _SEEDED_POOLS.items():
    question_cache.set(t, d, q_list)
    # Also seed Easy and Hard variants
    question_cache.set(t, "easy", q_list)
    question_cache.set(t, "hard", q_list)


def build_assessment_prompt(topic: str, difficulty: str) -> str:
    return f"""
You are an experienced assessment designer responsible for creating
accurate, fair, and educational multiple-choice assessments.

ASSESSMENT REQUIREMENTS
- Topic: {topic}
- Difficulty: {difficulty}
- Number of questions: exactly 5
- Options per question: exactly 4
- Correct answers per question: exactly 1

QUESTION DESIGN RULES
1. Generate five distinct questions relevant to the requested topic.
2. Keep every question focused on one clearly testable concept.
3. Match the requested difficulty:
   - Easy: test foundational knowledge and basic understanding.
   - Medium: test application, interpretation, and conceptual understanding.
   - Hard: test deeper reasoning, analysis, or application to less familiar cases.
4. Use precise, unambiguous wording.
5. Ensure each question can be answered using the information in its
   wording and established knowledge of the topic.
6. Provide exactly four distinct, plausible options for every question.
7. Ensure exactly one option is correct. The other three must be incorrect
   but plausible, and must not be alternative valid answers.
8. The correct_answer value must match one of the four options exactly.
9. Provide a concise explanation that establishes why the correct answer
   is correct.
10. Avoid repeated questions, superficial rewordings, duplicate options,
    trick questions, and unsupported factual claims.
11. Distribute correct answers across option positions where practical.
    Do not make the correct answer consistently the first option.

OUTPUT FORMAT
Return ONLY a valid JSON array containing exactly five objects.

Each object must have exactly these fields:
- "question": a non-empty string
- "options": an array of exactly four distinct strings
- "correct_answer": a string matching exactly one element in "options"
- "explanation": a non-empty string

The output must be directly parseable by Python's json.loads().
Use double quotes for JSON strings and escape special characters correctly.
Do not include Markdown fences, comments, trailing commas, or text outside
the JSON array.

Before returning, verify internally that:
- There are exactly five question objects.
- Every object contains all four required fields.
- Every question has exactly four distinct options.
- Every correct_answer matches one option exactly.
- Each question has exactly one defensible correct answer.
- All five questions are relevant to the requested topic and difficulty.

Return the JSON array only.
"""


SYSTEM_MESSAGE_CONTENT = (
    "You are a careful educational assessment designer. "
    "Follow the requested topic, difficulty, question count, and output schema. "
    "Prioritize factual accuracy, clear wording, distinct questions, "
    "and exactly one defensible correct answer per question. "
    "Return only valid JSON in the requested format."
)


def _parse_and_validate_raw_content(content: str, topic: str) -> list[Question]:
    """Clean, parse, and validate question JSON output."""
    if not content or not content.strip():
        raise ValueError("Groq returned an empty response.")

    cleaned_content = content.strip()
    if cleaned_content.startswith("```"):
        cleaned_content = (
            cleaned_content.removeprefix("```json")
            .removeprefix("```")
            .removesuffix("```")
            .strip()
        )

    parsed_response = json.loads(cleaned_content)

    if isinstance(parsed_response, list):
        raw_questions = parsed_response
    elif isinstance(parsed_response, dict):
        raw_questions = parsed_response.get("questions")
        if not isinstance(raw_questions, list):
            for val in parsed_response.values():
                if isinstance(val, list):
                    raw_questions = val
                    break
    else:
        raise TypeError("Groq response must be a JSON array or object.")

    if not isinstance(raw_questions, list):
        raise TypeError("Groq response must contain a list of questions.")

    if len(raw_questions) != 5:
        raise TypeError("Groq must return exactly 5 questions.")

    # 1. Pydantic schema validation
    questions = question_adapter.validate_python(raw_questions)

    # 2. Defensibility and grounding guardrail validation
    validated_questions = validate_question_grounding(questions, topic)

    return validated_questions


async def generate_questions(
    topic: str,
    difficulty: str = "Medium",
    use_cache: bool = True,
) -> list[Question]:
    """
    Generate five validated quiz questions asynchronously using Groq.
    Leverages caching for low latency and concurrency protection.
    """
    if use_cache:
        cached = question_cache.get(topic, difficulty)
        if cached:
            return cached

    prompt = build_assessment_prompt(topic, difficulty)
    response = None

    async with _groq_semaphore:
        for attempt in range(MAX_ATTEMPTS):
            try:
                response = await async_client.chat.completions.create(
                    model="openai/gpt-oss-120b",
                    response_format={"type": "json_object"},
                    messages=[
                        {
                            "role": "system",
                            "content": SYSTEM_MESSAGE_CONTENT,
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

                delay = (2 ** (attempt + 1)) + random.uniform(0, 1)
                await asyncio.sleep(delay)

    if response is None:
        raise RuntimeError("Groq did not return a response.")

    content = response.choices[0].message.content
    questions = _parse_and_validate_raw_content(content, topic)

    if use_cache:
        question_cache.set(topic, difficulty, questions)

    return questions


def generate_questions_sync(
    topic: str,
    difficulty: str = "Medium",
    use_cache: bool = True,
) -> list[Question]:
    """Synchronous fallback generator using Groq sync client."""
    if use_cache:
        cached = question_cache.get(topic, difficulty)
        if cached:
            return cached

    prompt = build_assessment_prompt(topic, difficulty)
    response = None

    for attempt in range(MAX_ATTEMPTS):
        try:
            response = sync_client.chat.completions.create(
                model="openai/gpt-oss-120b",
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": SYSTEM_MESSAGE_CONTENT,
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

            delay = (2 ** (attempt + 1)) + random.uniform(0, 1)
            time.sleep(delay)

    if response is None:
        raise RuntimeError("Groq did not return a response.")

    content = response.choices[0].message.content
    questions = _parse_and_validate_raw_content(content, topic)

    if use_cache:
        question_cache.set(topic, difficulty, questions)

    return questions
