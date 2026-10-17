
const quizSetup = document.getElementById("quiz-setup");
const quizForm = document.getElementById("quiz-form");
const quizScreen = document.getElementById("quiz-screen");

let questions = [];
let currentQuestionIndex = 0;
let selectedAnswers = [];
let currentQuizId = null;

function showQuizSetup() {
    quizSetup.hidden = false;
    quizSetup.scrollIntoView({
        behavior: "smooth",
        block: "start"
    });

    document.getElementById("topic").focus();
}

function getOrCreateReviewContainer() {
    let container = document.getElementById("results-review");

    if (!container) {
        container = document.createElement("div");
        container.id = "results-review";
        container.style.marginTop = "28px";

        const tryAgainButton = document.getElementById("try-again");
        resultsScreen.insertBefore(container, tryAgainButton);
    }

    return container;
}

quizForm.addEventListener("submit", async function (event) {
    event.preventDefault();

    const topicInput = document.getElementById("topic");
    const customTopicInput = document.getElementById("custom-topic");
    const difficultyInput = document.getElementById("difficulty");
    const submitButton = quizForm.querySelector('button[type="submit"]');

    const topic = topicInput.value === "Other"
        ? customTopicInput.value.trim()
        : topicInput.value;

    const difficulty = difficultyInput.value;

    if (!topic) {
        customTopicInput.setCustomValidity("Please enter a topic.");
        customTopicInput.reportValidity();
        customTopicInput.setCustomValidity("");
        return;
    }

    submitButton.disabled = true;
    submitButton.textContent = "Generating questions...";

    try {
        const response = await fetch("http://127.0.0.1:8000/quiz/generate", {
            method: "POST",
            credentials: "include",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ topic, difficulty })
        });

        const quizData = await response.json();

        if (!response.ok) {
            throw new Error(
                quizData.detail || "Could not generate questions."
            );
        }

        if (!quizData.questions || quizData.questions.length !== 5) {
            throw new Error("The quiz must contain exactly five questions.");
        }

        questions = quizData.questions;
        currentQuestionIndex = 0;
        selectedAnswers = Array(questions.length).fill(null);
        currentQuizId = quizData.quiz_id;

        document.getElementById("quiz-topic").textContent = topic;

        quizSetup.hidden = true;
        resultsScreen.hidden = true;
        quizScreen.hidden = false;

        renderQuestion();

        quizScreen.scrollIntoView({
            behavior: "smooth",
            block: "start"
        });
    } catch (error) {
        console.error("Quiz generation error:", error);
        alert(error.message || "Could not generate questions. Please try again.");
    } finally {
        submitButton.disabled = false;
        submitButton.textContent = "Generate questions →";
    }
});



// ================================
// Google Authentication - Profile
// ================================

const profileButton = document.getElementById("profile-button");
const profileDropdown = document.getElementById("profile-dropdown");
const profileName = document.getElementById("profile-name");
const profileEmail = document.getElementById("profile-email");
const profilePicture = document.getElementById("profile-picture");
const googleLoginButton = document.getElementById("google-login-button");
const logoutButton = document.getElementById("logout-button");

const AUTH_API = "http://127.0.0.1:8000";

async function loadUserProfile() {
    try {
        const response = await fetch(`${AUTH_API}/auth/me`, {
            credentials: "include"
        });

        if (!response.ok) {
            if (response.status !== 401) {
                console.error("Could not load user profile.");
            }

            showLoggedOutProfile();
            return;
        }

        const data = await response.json();
        const user = data.user;

        profileName.textContent = user.name || "Google User";
        profileEmail.textContent = user.email || "";

        if (user.picture) {
            profilePicture.src = user.picture;
            profilePicture.hidden = false;
            profileButton.innerHTML = "";
            const avatarImage = document.createElement("img");
            avatarImage.src = user.picture;
            avatarImage.alt = "";
            profileButton.appendChild(avatarImage);
        } else {
            profilePicture.hidden = true;
            profileButton.textContent =
                (user.name || "U").trim().charAt(0).toUpperCase();
        }

        googleLoginButton.hidden = true;
        logoutButton.hidden = false;
    } catch (error) {
        console.error("Authentication status check failed:", error);
        showLoggedOutProfile();
    }
}

function showLoggedOutProfile() {
    profileName.textContent = "Guest";
    profileEmail.textContent = "";

    profilePicture.hidden = true;
    profileButton.textContent = "U";

    googleLoginButton.hidden = false;
    logoutButton.hidden = true;
}

profileButton.addEventListener("click", () => {
    const isOpening = profileDropdown.hidden;

    profileDropdown.hidden = !isOpening;
    profileButton.setAttribute("aria-expanded", String(isOpening));
});

googleLoginButton.addEventListener("click", () => {
    window.location.href = `${AUTH_API}/auth/google/login`;
});

logoutButton.addEventListener("click", async () => {
    logoutButton.disabled = true;
    logoutButton.textContent = "Signing out...";

    try {
        const response = await fetch(`${AUTH_API}/auth/logout`, {
            method: "POST",
            credentials: "include"
        });

        if (!response.ok) {
            throw new Error("Could not sign out. Please try again.");
        }

        showLoggedOutProfile();
        profileDropdown.hidden = true;
        profileButton.setAttribute("aria-expanded", "false");
    } catch (error) {
        console.error("Logout failed:", error);
        alert(error.message || "Could not sign out.");
    } finally {
        logoutButton.disabled = false;
        logoutButton.textContent = "Sign out";
    }
});

document.addEventListener("click", (event) => {
    if (
        !event.target.closest(".profile-container") &&
        !profileDropdown.hidden
    ) {
        profileDropdown.hidden = true;
        profileButton.setAttribute("aria-expanded", "false");
    }
});

// Check the current session when the dashboard loads.
loadUserProfile();




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

    const unanswered = selectedAnswers.filter(
        answer => answer === null
    ).length;

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
            credentials: "include",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                quiz_id: currentQuizId,
                selected_answers: selectedAnswers
            })
        });

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.detail || "Could not submit quiz.");
        }

        if (!Array.isArray(result.questions) || result.questions.length !== 5) {
            throw new Error(
                "The quiz was submitted, but detailed results were not returned. " +
                "Please check the backend response."
            );
        }

        // Only display correct answers after the backend accepts submission.
        document.getElementById("result-score").textContent =
            `${result.score} / ${result.total_questions}`;

        document.getElementById("result-percentage").textContent =
            `${result.percentage}%`;

        document.getElementById("result-summary").textContent =
            `${result.correct_count} correct · ${result.incorrect_count} incorrect`;

        renderResultsReview(result.questions);

        quizScreen.hidden = true;
        resultsScreen.hidden = false;

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

function renderResultsReview(questionReviews) {
    const container = getOrCreateReviewContainer();
    container.replaceChildren();

    const heading = document.createElement("h2");
    heading.textContent = "Review your answers";
    heading.style.marginBottom = "20px";
    container.appendChild(heading);

    questionReviews.forEach((review) => {
        const card = document.createElement("article");
        card.style.padding = "20px";
        card.style.marginBottom = "18px";
        card.style.border = "1px solid #e2e8f0";
        card.style.borderRadius = "12px";
        card.style.background = "#ffffff";

        const title = document.createElement("h3");
        title.textContent = `Question ${review.question_number}`;
        title.style.marginBottom = "12px";
        card.appendChild(title);

        const questionText = document.createElement("p");
        questionText.textContent = review.question;
        questionText.style.whiteSpace = "pre-wrap";
        questionText.style.lineHeight = "1.6";
        questionText.style.marginBottom = "16px";
        card.appendChild(questionText);

        const status = document.createElement("p");
        status.textContent = review.is_correct
            ? "✓ Correct answer"
            : review.selected_answer === null
                ? "Not answered"
                : "✗ Incorrect answer";

        status.style.fontWeight = "600";
        status.style.color = review.is_correct
            ? "#15803d"
            : "#b91c1c";
        status.style.marginBottom = "12px";
        card.appendChild(status);

        const optionsList = document.createElement("div");
        optionsList.style.display = "grid";
        optionsList.style.gap = "8px";

        review.options.forEach((option) => {
            const optionRow = document.createElement("div");
            optionRow.style.padding = "12px";
            optionRow.style.border = "1px solid #e2e8f0";
            optionRow.style.borderRadius = "8px";
            optionRow.style.lineHeight = "1.5";

            const isCorrect = option.is_correct;
            const isWrongSelection = option.is_selected && !isCorrect;

            if (isCorrect) {
                optionRow.style.background = "#dcfce7";
                optionRow.style.borderColor = "#16a34a";
            } else if (isWrongSelection) {
                optionRow.style.background = "#fee2e2";
                optionRow.style.borderColor = "#dc2626";
            } else {
                optionRow.style.background = "#f8fafc";
            }

            const optionLabel = document.createElement("strong");
            optionLabel.textContent = `${option.label}. `;
            optionRow.appendChild(optionLabel);

            const optionContent = document.createElement("span");
            optionContent.textContent = option.text;
            optionRow.appendChild(optionContent);

            const markers = [];

            if (isCorrect) markers.push("Correct answer");
            if (option.is_selected) markers.push("Your answer");

            if (markers.length > 0) {
                const marker = document.createElement("span");
                marker.textContent = ` — ${markers.join(" · ")}`;
                marker.style.fontWeight = "600";
                marker.style.color = isCorrect ? "#166534" : "#991b1b";
                optionRow.appendChild(marker);
            }

            optionsList.appendChild(optionRow);
        });

        card.appendChild(optionsList);

        const explanationTitle = document.createElement("h4");
        explanationTitle.textContent = "Explanation";
        explanationTitle.style.marginTop = "18px";
        explanationTitle.style.marginBottom = "8px";
        card.appendChild(explanationTitle);

        const explanation = document.createElement("p");
        explanation.textContent =
            review.explanation || "No explanation is available.";
        explanation.style.lineHeight = "1.6";
        explanation.style.whiteSpace = "pre-wrap";
        card.appendChild(explanation);

        container.appendChild(card);
    });
}

document.getElementById("try-again").addEventListener("click", () => {
    questions = [];
    selectedAnswers = [];
    currentQuestionIndex = 0;
    currentQuizId = null;

    document.getElementById("results-review")?.replaceChildren();

    resultsScreen.hidden = true;
    quizScreen.hidden = true;
    quizSetup.hidden = false;

    quizSetup.scrollIntoView({
        behavior: "smooth",
        block: "start"
    });

    document.getElementById("topic").focus();
});

