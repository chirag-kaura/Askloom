// ==========================================
// Askloom - Frontend Application Logic
// ==========================================

const quizSetup = document.getElementById("quiz-setup");
const quizForm = document.getElementById("quiz-form");
const quizScreen = document.getElementById("quiz-screen");
const resultsScreen = document.getElementById("results-screen");

const AUTH_API = window.location.hostname === "localhost"
    ? "http://localhost:8000"
    : "http://127.0.0.1:8000";

let questions = [];
let currentQuestionIndex = 0;
let selectedAnswers = [];
let currentQuizId = null;
let currentUser = null;
let cachedAssessments = [];

// ==========================================
// Utility Helpers
// ==========================================

function escapeHtml(str) {
    if (str === null || str === undefined) return "";
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function formatDate(isoString) {
    if (!isoString) return "—";
    try {
        const d = new Date(isoString);
        return d.toLocaleDateString(undefined, {
            month: "short",
            day: "numeric",
            year: "numeric"
        });
    } catch {
        return "—";
    }
}

function formatJoinedDate(isoString) {
    if (!isoString) return "Member since: Recently";
    try {
        const d = new Date(isoString);
        return "Member since: " + d.toLocaleDateString(undefined, {
            month: "long",
            year: "numeric"
        });
    } catch {
        return "Member since: Recently";
    }
}

function getOrCreateReviewContainer() {
    let container = document.getElementById("results-review");
    if (!container) {
        container = document.createElement("div");
        container.id = "results-review";
        container.style.marginTop = "28px";

        const tryAgainButton = document.getElementById("try-again");
        if (tryAgainButton && tryAgainButton.parentElement) {
            resultsScreen.insertBefore(container, tryAgainButton.parentElement);
        } else {
            resultsScreen.appendChild(container);
        }
    }
    return container;
}

// ==========================================
// Single Page Application (SPA) Router
// ==========================================

function navigateToView(viewName, updateHash = true) {
    const target = (viewName || "dashboard").toLowerCase();
    const validViews = ["dashboard", "assessments", "profile"];
    const activeView = validViews.includes(target) ? target : "dashboard";

    // 1. Hide all main views and quiz screens
    document.querySelectorAll(".app-view").forEach(el => {
        el.hidden = true;
    });
    if (quizScreen) quizScreen.hidden = true;
    if (resultsScreen) resultsScreen.hidden = true;

    // 2. Display the selected view
    const targetEl = document.getElementById(`view-${activeView}`);
    if (targetEl) {
        targetEl.hidden = false;
    }

    // 3. Update topbar typography and title
    const topbarTitle = document.getElementById("topbar-title");
    const topbarEyebrow = document.getElementById("topbar-eyebrow");

    if (activeView === "dashboard") {
        if (topbarEyebrow) topbarEyebrow.textContent = "YOUR LEARNING SPACE";
        if (topbarTitle) topbarTitle.textContent = "Dashboard";
        document.title = "Askloom | Dashboard";
        loadDashboardData();
    } else if (activeView === "assessments") {
        if (topbarEyebrow) topbarEyebrow.textContent = "PRACTICE ARCHIVE";
        if (topbarTitle) topbarTitle.textContent = "My Assessments";
        document.title = "Askloom | My Assessments";
        loadAssessmentsView();
    } else if (activeView === "profile") {
        if (topbarEyebrow) topbarEyebrow.textContent = "ACCOUNT & METRICS";
        if (topbarTitle) topbarTitle.textContent = "Profile & Analytics";
        document.title = "Askloom | Profile";
        loadProfileView();
    }

    // 4. Update sidebar navigation link active state
    document.querySelectorAll(".sidebar nav .nav-link").forEach(link => {
        if (link.getAttribute("data-view") === activeView) {
            link.classList.add("active");
        } else {
            link.classList.remove("active");
        }
    });

    // 5. Synchronize URL hash
    if (updateHash) {
        const expectedHash = activeView === "dashboard" ? "" : `#${activeView}`;
        if (activeView === "dashboard") {
            if (window.location.hash) {
                history.pushState(null, "", window.location.pathname);
            }
        } else if (window.location.hash !== expectedHash) {
            window.location.hash = activeView;
        }
    }
}

function initRouter() {
    // Intercept sidebar navigation clicks
    document.querySelectorAll(".sidebar nav .nav-link").forEach(link => {
        link.addEventListener("click", (e) => {
            const view = link.getAttribute("data-view");
            if (view) {
                e.preventDefault();
                navigateToView(view, true);
            }
        });
    });

    // Listen for hash changes (browser back/forward or manual hash navigation)
    window.addEventListener("hashchange", () => {
        const hash = window.location.hash.replace("#", "").toLowerCase();
        navigateToView(hash || "dashboard", false);
    });

    // Handle initial route on page load
    const initialHash = window.location.hash.replace("#", "").toLowerCase();
    navigateToView(initialHash || "dashboard", false);
}

// ==========================================
// Quiz Setup Controls
// ==========================================

function showQuizSetup() {
    if (quizSetup) {
        quizSetup.hidden = false;
        quizSetup.scrollIntoView({
            behavior: "smooth",
            block: "start"
        });
        const topicSelect = document.getElementById("topic");
        if (topicSelect) topicSelect.focus();
    }
}

function cancelQuizSetup() {
    if (quizSetup) {
        quizSetup.hidden = true;
    }
}

const topicSelect = document.getElementById("topic");
const customTopicContainer = document.getElementById("custom-topic-container");
const customTopicInput = document.getElementById("custom-topic");

if (topicSelect) {
    topicSelect.addEventListener("change", () => {
        topicSelect.setCustomValidity("");
        const val = (topicSelect.value || "").toLowerCase();
        if (val === "others" || val === "other") {
            customTopicContainer.hidden = false;
            customTopicInput.required = true;
            customTopicInput.focus();
        } else {
            customTopicContainer.hidden = true;
            customTopicInput.required = false;
            customTopicInput.value = "";
        }
    });
}

if (customTopicInput) {
    customTopicInput.addEventListener("input", () => {
        customTopicInput.setCustomValidity("");
    });
}

// ==========================================
// Dashboard View Data & Rendering
// ==========================================

async function loadDashboardData() {
    // 1. Fetch live metrics
    try {
        const statsRes = await fetch(`${AUTH_API}/quiz/stats`, {
            credentials: "include"
        });
        if (statsRes.ok) {
            const stats = await statsRes.json();
            const totalEl = document.getElementById("total-assessments");
            const completedEl = document.getElementById("completed-assessments");
            const avgEl = document.getElementById("average-score");

            if (totalEl) totalEl.textContent = stats.total_assessments ?? 0;
            if (completedEl) completedEl.textContent = stats.completed_assessments ?? 0;
            if (avgEl) {
                avgEl.textContent = stats.average_score !== null && stats.average_score !== undefined
                    ? `${stats.average_score}%`
                    : "—";
            }
        }
    } catch (err) {
        console.error("Error loading dashboard stats:", err);
    }

    // 2. Fetch recent assessments (top 5)
    try {
        const histRes = await fetch(`${AUTH_API}/quiz/history`, {
            credentials: "include"
        });
        if (histRes.ok) {
            const data = await histRes.json();
            const list = data.assessments || [];
            cachedAssessments = list;
            renderRecentAssessmentsTable(list.slice(0, 5));
        } else {
            renderRecentAssessmentsTable([]);
        }
    } catch (err) {
        console.error("Error loading recent assessments:", err);
        renderRecentAssessmentsTable([]);
    }
}

function renderRecentAssessmentsTable(assessments) {
    const tbody = document.getElementById("dashboard-recent-history");
    if (!tbody) return;

    if (!assessments || assessments.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="6" class="empty-state">
                    No assessments yet. Click <strong>Start an assessment</strong> to begin practicing!
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = assessments.map(item => {
        const diffClass = `badge-${(item.difficulty || "medium").toLowerCase()}`;
        const isCompleted = item.status === "completed";
        const statusClass = isCompleted ? "badge-completed" : "badge-in-progress";
        const statusLabel = isCompleted ? "Completed" : "In Progress";
        const scoreDisplay = isCompleted ? `${item.score} / ${item.total_questions}` : "—";
        const dateDisplay = formatDate(item.completed_at || item.started_at);

        return `
            <tr>
                <td><strong>${escapeHtml(item.topic)}</strong></td>
                <td><span class="badge-diff ${diffClass}">${escapeHtml(item.difficulty)}</span></td>
                <td>${dateDisplay}</td>
                <td>${scoreDisplay}</td>
                <td><span class="badge-status ${statusClass}">${statusLabel}</span></td>
                <td>
                    ${isCompleted
                        ? `<button type="button" class="review-btn" onclick="openPastQuizReview('${item.assessment_id}')">Review</button>`
                        : `<span style="color: var(--text-secondary); font-size: 12px;">In progress</span>`
                    }
                </td>
            </tr>
        `;
    }).join("");
}

// ==========================================
// My Assessments View: Data & Filters
// ==========================================

async function loadAssessmentsView() {
    const tbody = document.getElementById("my-assessments-history");
    if (tbody && cachedAssessments.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7" class="empty-state">
                    Loading your assessments...
                </td>
            </tr>
        `;
    }

    try {
        const response = await fetch(`${AUTH_API}/quiz/history`, {
            credentials: "include"
        });

        if (!response.ok) {
            if (response.status === 401) {
                cachedAssessments = [];
                if (tbody) {
                    tbody.innerHTML = `
                        <tr>
                            <td colspan="7" class="empty-state">
                                Please sign in with Google to view and manage your assessment history.
                            </td>
                        </tr>
                    `;
                }
                return;
            }
            throw new Error("Could not load assessments history.");
        }

        const data = await response.json();
        cachedAssessments = data.assessments || [];
        applyAssessmentsFilters();
    } catch (error) {
        console.error("Error loading assessments view:", error);
        if (tbody) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="7" class="empty-state">
                        Failed to load assessments. Please try again.
                    </td>
                </tr>
            `;
        }
    }
}

function applyAssessmentsFilters() {
    const searchInput = document.getElementById("assessment-search");
    const diffFilter = document.getElementById("assessment-filter-difficulty");
    const statusFilter = document.getElementById("assessment-filter-status");

    const query = (searchInput?.value || "").trim().toLowerCase();
    const diff = (diffFilter?.value || "").toLowerCase();
    const status = (statusFilter?.value || "").toLowerCase();

    const filtered = cachedAssessments.filter(item => {
        const matchesQuery = !query || (item.topic && item.topic.toLowerCase().includes(query));
        const matchesDiff = !diff || (item.difficulty && item.difficulty.toLowerCase() === diff);
        const matchesStatus = !status || (item.status && item.status.toLowerCase() === status);
        return matchesQuery && matchesDiff && matchesStatus;
    });

    renderAssessmentsTable(filtered);
}

function renderAssessmentsTable(assessments) {
    const tbody = document.getElementById("my-assessments-history");
    if (!tbody) return;

    if (!assessments || assessments.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7" class="empty-state">
                    No assessments found matching your filter criteria.
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = assessments.map(item => {
        const diffClass = `badge-${(item.difficulty || "medium").toLowerCase()}`;
        const isCompleted = item.status === "completed";
        const statusClass = isCompleted ? "badge-completed" : "badge-in-progress";
        const statusLabel = isCompleted ? "Completed" : "In Progress";
        const scoreDisplay = isCompleted ? `${item.score} / ${item.total_questions}` : "—";
        const pct = item.percentage !== null && item.percentage !== undefined ? item.percentage : 0;

        let pillClass = "score-mid";
        if (pct >= 80) pillClass = "score-high";
        else if (pct < 60) pillClass = "score-low";

        const accuracyDisplay = isCompleted
            ? `<span class="score-pill ${pillClass}">${pct}%</span>`
            : "—";

        const dateDisplay = formatDate(item.completed_at || item.started_at);

        return `
            <tr>
                <td><strong>${escapeHtml(item.topic)}</strong></td>
                <td><span class="badge-diff ${diffClass}">${escapeHtml(item.difficulty)}</span></td>
                <td>${dateDisplay}</td>
                <td>${scoreDisplay}</td>
                <td>${accuracyDisplay}</td>
                <td><span class="badge-status ${statusClass}">${statusLabel}</span></td>
                <td>
                    ${isCompleted
                        ? `<button type="button" class="review-btn" onclick="openPastQuizReview('${item.assessment_id}')">Review</button>`
                        : `<span style="color: var(--text-secondary); font-size: 12px;">In progress</span>`
                    }
                </td>
            </tr>
        `;
    }).join("");
}

// Bind filter event listeners
const assessmentSearchInput = document.getElementById("assessment-search");
if (assessmentSearchInput) {
    assessmentSearchInput.addEventListener("input", applyAssessmentsFilters);
}
const assessmentDiffFilter = document.getElementById("assessment-filter-difficulty");
if (assessmentDiffFilter) {
    assessmentDiffFilter.addEventListener("change", applyAssessmentsFilters);
}
const assessmentStatusFilter = document.getElementById("assessment-filter-status");
if (assessmentStatusFilter) {
    assessmentStatusFilter.addEventListener("change", applyAssessmentsFilters);
}

// ==========================================
// Profile View: Metrics & Account Connection
// ==========================================

async function loadProfileView() {
    const avatarEl = document.getElementById("profile-hero-avatar");
    const nameEl = document.getElementById("profile-hero-name");
    const emailEl = document.getElementById("profile-hero-email");
    const verifiedBadge = document.getElementById("profile-verified-badge");
    const joinedEl = document.getElementById("profile-hero-joined");
    const statTotalEl = document.getElementById("profile-stat-total");
    const statCompletedEl = document.getElementById("profile-stat-completed");
    const statScoreEl = document.getElementById("profile-stat-score");
    const statTopicEl = document.getElementById("profile-stat-topic");
    const profileLoginBtn = document.getElementById("profile-google-login-btn");
    const profileLogoutBtn = document.getElementById("profile-logout-btn");

    try {
        const meRes = await fetch(`${AUTH_API}/auth/me`, {
            credentials: "include"
        });

        if (meRes.ok) {
            const meData = await meRes.json();
            const user = meData.user;
            currentUser = user;

            if (nameEl) nameEl.textContent = user.name || "Google User";
            if (emailEl) emailEl.textContent = user.email || "";

            if (user.picture && avatarEl) {
                avatarEl.innerHTML = `<img src="${escapeHtml(user.picture)}" alt="Profile picture">`;
            } else if (avatarEl) {
                avatarEl.textContent = (user.name || "U").trim().charAt(0).toUpperCase();
            }

            if (verifiedBadge) {
                verifiedBadge.textContent = "Google Verified";
                verifiedBadge.className = "badge-status badge-completed";
            }

            if (joinedEl) {
                joinedEl.textContent = formatJoinedDate(user.created_at);
            }

            if (profileLoginBtn) profileLoginBtn.hidden = true;
            if (profileLogoutBtn) profileLogoutBtn.hidden = false;
        } else {
            currentUser = null;
            if (nameEl) nameEl.textContent = "Guest User";
            if (emailEl) emailEl.textContent = "Not signed in";
            if (avatarEl) avatarEl.textContent = "U";
            if (verifiedBadge) {
                verifiedBadge.textContent = "Guest Mode";
                verifiedBadge.className = "badge-status badge-in-progress";
            }
            if (joinedEl) joinedEl.textContent = "Session: Temporary";
            if (profileLoginBtn) profileLoginBtn.hidden = false;
            if (profileLogoutBtn) profileLogoutBtn.hidden = true;
        }

        // Fetch user learning metrics
        const statsRes = await fetch(`${AUTH_API}/quiz/stats`, {
            credentials: "include"
        });
        if (statsRes.ok) {
            const stats = await statsRes.json();
            if (statTotalEl) statTotalEl.textContent = stats.total_assessments ?? 0;
            const completionRate = stats.total_assessments > 0
                ? Math.round((stats.completed_assessments / stats.total_assessments) * 100)
                : 0;
            if (statCompletedEl) statCompletedEl.textContent = `${completionRate}%`;
            if (statScoreEl) {
                statScoreEl.textContent = stats.average_score !== null && stats.average_score !== undefined
                    ? `${stats.average_score}%`
                    : "—";
            }
            if (statTopicEl) {
                statTopicEl.textContent = stats.favorite_topic || "—";
                statTopicEl.title = stats.favorite_topic || "";
            }
        }
    } catch (error) {
        console.error("Error loading profile view:", error);
    }
}

// Profile Card Action Handlers
const profileGoogleLoginBtn = document.getElementById("profile-google-login-btn");
if (profileGoogleLoginBtn) {
    profileGoogleLoginBtn.addEventListener("click", () => {
        window.location.href = `${AUTH_API}/auth/google/login`;
    });
}

const profileLogoutBtn = document.getElementById("profile-logout-btn");
if (profileLogoutBtn) {
    profileLogoutBtn.addEventListener("click", async () => {
        profileLogoutBtn.disabled = true;
        profileLogoutBtn.textContent = "Signing out...";

        try {
            const response = await fetch(`${AUTH_API}/auth/logout`, {
                method: "POST",
                credentials: "include"
            });

            if (!response.ok) {
                throw new Error("Could not sign out. Please try again.");
            }

            showLoggedOutProfile();
            await loadProfileView();
            await loadDashboardData();
        } catch (error) {
            console.error("Profile sign out failed:", error);
            alert(error.message || "Could not sign out.");
        } finally {
            profileLogoutBtn.disabled = false;
            profileLogoutBtn.textContent = "Sign out of Google";
        }
    });
}

// ==========================================
// Review Past Assessment
// ==========================================

async function openPastQuizReview(quizId) {
    try {
        const response = await fetch(`${AUTH_API}/quiz/review/${quizId}`, {
            credentials: "include"
        });

        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            throw new Error(errData.detail || "Could not load quiz review.");
        }

        const data = await response.json();

        // Update score & percentage card
        const scoreEl = document.getElementById("result-score");
        const pctEl = document.getElementById("result-percentage");
        const summaryEl = document.getElementById("result-summary");
        const titleEl = document.getElementById("results-title");
        const subtitleEl = document.getElementById("results-subtitle");

        if (scoreEl) scoreEl.textContent = `${data.score} / ${data.total_questions}`;
        if (pctEl) pctEl.textContent = `${data.percentage}%`;
        if (summaryEl) {
            summaryEl.textContent = `${data.correct_count} correct · ${data.incorrect_count} incorrect`;
        }
        if (titleEl) titleEl.textContent = `${data.topic} Review`;
        if (subtitleEl) {
            subtitleEl.textContent = `${data.difficulty} · Completed ${formatDate(data.completed_at || data.started_at)}`;
        }

        // Render question reviews
        renderResultsReview(data.questions);

        // Hide main app views and show results screen
        document.querySelectorAll(".app-view").forEach(v => v.hidden = true);
        if (quizSetup) quizSetup.hidden = true;
        if (quizScreen) quizScreen.hidden = true;

        resultsScreen.hidden = false;
        resultsScreen.scrollIntoView({
            behavior: "smooth",
            block: "start"
        });
    } catch (error) {
        console.error("Error opening assessment review:", error);
        alert(error.message || "Could not open assessment review.");
    }
}

// ==========================================
// Live Quiz Generation & Execution Flow
// ==========================================

quizForm.addEventListener("submit", async function (event) {
    event.preventDefault();

    const topicInput = document.getElementById("topic");
    const customTopicInput = document.getElementById("custom-topic");
    const difficultyInput = document.getElementById("difficulty");
    const submitButton = quizForm.querySelector('button[type="submit"]');

    const selectedVal = (topicInput.value || "").toLowerCase();
    const isOther = selectedVal === "others" || selectedVal === "other";

    if (!topicInput.value) {
        topicInput.setCustomValidity("Please select a subject from the list.");
        topicInput.reportValidity();
        topicInput.setCustomValidity("");
        return;
    }

    const topic = isOther
        ? customTopicInput.value.trim()
        : topicInput.value;

    const difficulty = difficultyInput.value;

    if (isOther && !topic) {
        customTopicInput.setCustomValidity("Please enter your topic of interest.");
        customTopicInput.reportValidity();
        customTopicInput.setCustomValidity("");
        return;
    }

    submitButton.disabled = true;
    submitButton.textContent = "Generating questions...";

    try {
        const response = await fetch(`${AUTH_API}/quiz/generate`, {
            method: "POST",
            credentials: "include",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ topic, difficulty })
        });

        const quizData = await response.json();

        if (!response.ok) {
            if (response.status === 401) {
                profileDropdown.hidden = false;
                profileButton.setAttribute("aria-expanded", "true");
                throw new Error("Please sign in with Google to create an assessment.");
            }
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

        // Hide all views and reveal quiz screen
        document.querySelectorAll(".app-view").forEach(v => v.hidden = true);
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
        const response = await fetch(`${AUTH_API}/quiz/submit`, {
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
            if (response.status === 401) {
                profileDropdown.hidden = false;
                profileButton.setAttribute("aria-expanded", "true");
                throw new Error("Your session has expired. Please sign in again.");
            }
            throw new Error(result.detail || "Could not submit quiz.");
        }

        if (!Array.isArray(result.questions) || result.questions.length !== 5) {
            throw new Error(
                "The quiz was submitted, but detailed results were not returned. " +
                "Please check the backend response."
            );
        }

        // Set live quiz results headers
        const titleEl = document.getElementById("results-title");
        const subtitleEl = document.getElementById("results-subtitle");
        if (titleEl) titleEl.textContent = "Your results";
        if (subtitleEl) subtitleEl.textContent = "Here's how you performed in this assessment.";

        document.getElementById("result-score").textContent =
            `${result.score} / ${result.total_questions}`;

        document.getElementById("result-percentage").textContent =
            `${result.percentage}%`;

        document.getElementById("result-summary").textContent =
            `${result.correct_count} correct · ${result.incorrect_count} incorrect`;

        renderResultsReview(result.questions);

        quizScreen.hidden = true;
        resultsScreen.hidden = false;

        // Refresh stats and history in background
        loadDashboardData();

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
    navigateToView("dashboard", true);
    showQuizSetup();
});

// ==========================================
// Google Authentication - Profile Dropdown
// ==========================================

const profileButton = document.getElementById("profile-button");
const profileDropdown = document.getElementById("profile-dropdown");
const profileName = document.getElementById("profile-name");
const profileEmail = document.getElementById("profile-email");
const profilePicture = document.getElementById("profile-picture");
const googleLoginButton = document.getElementById("google-login-button");
const logoutButton = document.getElementById("logout-button");

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
        currentUser = user;

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

        // Personalized dashboard greeting
        const welcomeGreeting = document.getElementById("welcome-greeting");
        const welcomeSubtext = document.getElementById("welcome-subtext");
        const firstName = (user.name || "there").split(" ")[0];
        if (welcomeGreeting) welcomeGreeting.textContent = `Welcome back, ${firstName}!`;
        if (welcomeSubtext) welcomeSubtext.textContent = "Ready to sharpen your skills? Pick a topic and test your knowledge.";
    } catch (error) {
        console.error("Authentication status check failed:", error);
        showLoggedOutProfile();
    }
}

function showLoggedOutProfile() {
    currentUser = null;
    profileName.textContent = "Guest";
    profileEmail.textContent = "";

    profilePicture.hidden = true;
    profileButton.textContent = "U";

    googleLoginButton.hidden = false;
    logoutButton.hidden = true;

    const welcomeGreeting = document.getElementById("welcome-greeting");
    const welcomeSubtext = document.getElementById("welcome-subtext");
    if (welcomeGreeting) welcomeGreeting.textContent = "Learn something new today.";
    if (welcomeSubtext) welcomeSubtext.textContent = "Practice your knowledge with AI-generated assessments.";
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
        await loadProfileView();
        await loadDashboardData();
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

// ==========================================
// Global Window Exports
// ==========================================

window.navigateToView = navigateToView;
window.showQuizSetup = showQuizSetup;
window.cancelQuizSetup = cancelQuizSetup;
window.openPastQuizReview = openPastQuizReview;

// Initialize session and route
loadUserProfile();
initRouter();
