
const quizSetup = document.getElementById("quiz-setup");
const quizForm = document.getElementById("quiz-form");
const quizScreen = document.getElementById("quiz-screen");

let questions = [];
let currentQuestionIndex = 0;
let selectedAnswers = [];

function showQuizSetup() {
    quizSetup.hidden = false;
    quizSetup.scrollIntoView({
        behavior: "smooth",
        block: "start"
    });

    document.getElementById("topic").focus();
}

quizForm.addEventListener("submit", async function (event) {
    event.preventDefault();

    const topicInput = document.getElementById("topic");
    const difficultyInput = document.getElementById("difficulty");
    const submitButton = quizForm.querySelector('button[type="submit"]');

    const topic = topicInput.value.trim() || "General Knowledge";
    const difficulty = difficultyInput.value;

    submitButton.disabled = true;
    submitButton.textContent = "Generating questions...";

    try {
        const response = await fetch("http://127.0.0.1:8000/quiz/generate", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ topic, difficulty })
        });

        if (!response.ok) {
            throw new Error(`Request failed: ${response.status}`);
        }

        const quizData = await response.json();

        questions = quizData.questions;
        currentQuestionIndex = 0;
        selectedAnswers = Array(questions.length).fill(null);

        // Keep the quiz ID for the scoring request later.
        window.currentQuizId = quizData.quiz_id;

        document.getElementById("quiz-topic").textContent = topic;

        quizSetup.hidden = true;
        quizScreen.hidden = false;

        renderQuestion();

        quizScreen.scrollIntoView({
            behavior: "smooth",
            block: "start"
        });

    } catch (error) {
        console.error("Quiz generation error:", error);
        alert("Could not generate questions. Please check the backend and try again.");
    } finally {
        submitButton.disabled = false;
        submitButton.textContent = "Generate questions →";
    }
});

function renderQuestion() {
    const question = questions[currentQuestionIndex];

    document.getElementById("question-progress").textContent =
        `Question ${currentQuestionIndex + 1} of ${questions.length}`;

    document.getElementById("question-text").textContent =
        question.question;

    document.getElementById("progress-bar").style.width =
        `${((currentQuestionIndex + 1) / questions.length) * 100}%`;

    const optionsContainer = document.getElementById("answer-options");
    optionsContainer.replaceChildren();

    question.options.forEach((option, optionIndex) => {
        const label = document.createElement("label");
        label.className = "answer-option";

        const radio = document.createElement("input");
        radio.type = "radio";
        radio.name = "answer";
        radio.value = option;
        radio.checked = selectedAnswers[currentQuestionIndex] === option;

        const optionText = document.createElement("span");
        optionText.textContent =
            `${String.fromCharCode(65 + optionIndex)}. ${option}`;

        radio.addEventListener("change", () => {
            selectedAnswers[currentQuestionIndex] = option;
        });

        label.append(radio, optionText);
        optionsContainer.appendChild(label);
    });

    document.getElementById("previous-question").disabled =
        currentQuestionIndex === 0;

    document.getElementById("next-question").textContent =
        currentQuestionIndex === questions.length - 1
            ? "Finish quiz"
            : "Next →";
}

document.getElementById("previous-question").addEventListener("click", () => {
    if (currentQuestionIndex > 0) {
        currentQuestionIndex--;
        renderQuestion();
    }
});


document.getElementById("next-question").addEventListener("click", async () => {
    if (currentQuestionIndex < questions.length - 1) {
        currentQuestionIndex++;
        renderQuestion();
        return;
    }

    const unanswered = selectedAnswers.filter(answer => answer === null).length;

    if (unanswered > 0) {
        const shouldSubmit = confirm(
            `You have ${unanswered} unanswered question(s). Submit anyway?`
        );

        if (!shouldSubmit) return;
    }

    const nextButton = document.getElementById("next-question");
    nextButton.disabled = true;
    nextButton.textContent = "Submitting...";

    try {
        const response = await fetch("http://127.0.0.1:8000/quiz/submit", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                quiz_id: window.currentQuizId,
                selected_answers: selectedAnswers
            })
        });

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.detail || "Could not submit quiz.");
        }

        quizScreen.hidden = true;

        const resultsScreen = document.getElementById("results-screen");
        resultsScreen.hidden = false;

        document.getElementById("result-score").textContent =
            `${result.score} / ${result.total_questions}`;

        document.getElementById("result-percentage").textContent =
            `${result.percentage}%`;

        document.getElementById("result-summary").textContent =
            `${result.correct_count} correct · ${result.incorrect_count} incorrect`;

        resultsScreen.scrollIntoView({
            behavior: "smooth",
            block: "start"
        });

    } catch (error) {
        console.error("Quiz submission error:", error);
        alert(error.message || "Could not submit quiz. Please try again.");
    } finally {
        nextButton.disabled = false;
        nextButton.textContent = "Finish quiz";
    }
});



document.getElementById("try-again").addEventListener("click", () => {
    quizScreen.hidden = true;
    document.getElementById("results-screen").hidden = true;
    quizSetup.hidden = false;

    quizForm.reset();
    questions = [];
    selectedAnswers = [];
    currentQuestionIndex = 0;
    window.currentQuizId = null;

    quizSetup.scrollIntoView({
        behavior: "smooth",
        block: "start"
    });

    document.getElementById("topic").focus();
});
