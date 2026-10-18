// ==========================================
// Askloom - Frontend Application Logic
// ==========================================

const quizSetup = document.getElementById("quiz-setup");
const quizForm = document.getElementById("quiz-form");
const quizScreen = document.getElementById("quiz-screen");
const resultsScreen = document.getElementById("results-screen");


const AUTH_API = (
    window.ASKLOOM_API_BASE_URL ||
    "https://askloom-backend-cqnl.onrender.com"
).replace(/\/$/, "");


let questions = [];
let currentQuestionIndex = 0;
let selectedAnswers = [];
let currentQuizId = null;
let currentUser = null;
let cachedAssessments = [];
let currentAlternatesRemaining = 3;
let slotVersions = [1, 1, 1, 1, 1];

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

function getPathView() {
    // Check if legacy hash was provided (e.g. #assessments, #profile)
    if (window.location.hash) {
        const rawHash = window.location.hash.replace("#", "").toLowerCase().trim();
        if (["dashboard", "assessments", "profile"].includes(rawHash)) {
            return rawHash;
        }
    }

    // Check URL pathname (e.g. /dashboard, /assessments, /profile)
    const path = window.location.pathname.replace(/^\/+|\/+$/g, "").toLowerCase().trim();
    if (["dashboard", "assessments", "profile"].includes(path)) {
        return path;
    }

    return "dashboard";
}

function navigateToView(viewName, updateUrl = true) {
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

    // 4. Update navigation links active state (sidebar & mobile nav)
    document.querySelectorAll(".sidebar nav .nav-link, .mobile-bottom-nav .mobile-nav-link").forEach(link => {
        if (link.getAttribute("data-view") === activeView) {
            link.classList.add("active");
        } else {
            link.classList.remove("active");
        }
    });

    // 5. Synchronize clean URL path (e.g. /dashboard, /assessments, /profile)
    const expectedPath = `/${activeView}`;
    if (updateUrl) {
        if (window.location.pathname !== expectedPath || window.location.hash) {
            history.pushState({ view: activeView }, "", expectedPath);
        }
    } else {
        if (window.location.pathname !== expectedPath || window.location.hash) {
            history.replaceState({ view: activeView }, "", expectedPath);
        }
    }
}

function initRouter() {
    // Intercept navigation links with data-view (sidebar links, mobile bottom nav, brand logos)
    document.querySelectorAll("[data-view]").forEach(link => {
        link.addEventListener("click", (e) => {
            const view = link.getAttribute("data-view");
            if (view && ["dashboard", "assessments", "profile"].includes(view)) {
                e.preventDefault();
                navigateToView(view, true);
                window.scrollTo({ top: 0, behavior: "smooth" });
            }
        });
    });

    // Listen for browser Back/Forward navigation
    window.addEventListener("popstate", (e) => {
        const targetView = (e.state && e.state.view) ? e.state.view : getPathView();
        navigateToView(targetView, false);
    });

    // Listen for hash changes if any legacy external links occur
    window.addEventListener("hashchange", () => {
        const targetView = getPathView();
        navigateToView(targetView, false);
    });

    // Handle initial route on page load
    const initialView = getPathView();
    navigateToView(initialView, false);
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
                        : `<button type="button" class="resume-btn" onclick="resumeAssessment('${item.assessment_id}')">Resume →</button>`
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
                        : `<button type="button" class="resume-btn" onclick="resumeAssessment('${item.assessment_id}')">Resume →</button>`
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
                avatarEl.innerHTML = `<img src="${escapeHtml(user.picture)}" alt="Profile picture" class="avatar-hero-img">`;
            } else if (avatarEl) {
                avatarEl.innerHTML = `<img src="/static/images/logo.png" alt="Profile avatar" class="avatar-hero-img">`;
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
            if (avatarEl) {
                avatarEl.innerHTML = `<img src="/static/images/logo.png" alt="Profile avatar" class="avatar-hero-img">`;
            }
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
            await loadAssessmentsView();
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
// Resume In-Progress Assessment
// ==========================================

async function resumeAssessment(quizId) {
    try {
        const response = await fetch(`${AUTH_API}/quiz/resume/${quizId}`, {
            credentials: "include"
        });

        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            throw new Error(errData.detail || "Could not resume assessment.");
        }

        const data = await response.json();
        questions = data.questions || [];
        if (!questions.length) {
            throw new Error("No questions found for this assessment.");
        }

        currentQuizId = data.quiz_id;
        selectedAnswers = data.selected_answers || Array(questions.length).fill(null);
        currentAlternatesRemaining = data.alternates_remaining ?? 3;
        slotVersions = [1, 1, 1, 1, 1];

        // Find the first unanswered question to resume from, or start at question 1
        const firstUnanswered = selectedAnswers.findIndex(a => a === null);
        currentQuestionIndex = firstUnanswered !== -1 ? firstUnanswered : 0;

        document.getElementById("quiz-topic").textContent = data.topic || "Assessment";

        // Hide all app views and reveal quiz screen
        document.querySelectorAll(".app-view").forEach(v => v.hidden = true);
        if (quizSetup) quizSetup.hidden = true;
        if (resultsScreen) resultsScreen.hidden = true;
        if (quizScreen) quizScreen.hidden = false;

        renderQuestion();

        quizScreen.scrollIntoView({
            behavior: "smooth",
            block: "start"
        });
    } catch (err) {
        console.error("Error resuming quiz:", err);
        alert(err.message || "Failed to resume quiz.");
    }
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
        currentAlternatesRemaining = 3;
        slotVersions = [1, 1, 1, 1, 1];

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

function updateAlternateButtonUI() {
    const altBtn = document.getElementById("alternate-question-btn");
    const counterBadge = document.getElementById("alternate-counter-badge");
    if (!altBtn || !counterBadge) return;

    counterBadge.textContent = `${currentAlternatesRemaining} left`;

    const slotVersion = slotVersions[currentQuestionIndex] || 1;
    if (currentAlternatesRemaining <= 0) {
        altBtn.disabled = true;
        altBtn.title = "All 3 alternate questions have been used for this assessment.";
    } else if (slotVersion >= 3) {
        altBtn.disabled = true;
        altBtn.title = "This question has reached its maximum version limit (3).";
    } else {
        altBtn.disabled = false;
        altBtn.title = `Generate an alternate question for Question ${currentQuestionIndex + 1} (${currentAlternatesRemaining} left)`;
    }
}

async function handleAlternateQuestion() {
    if (!currentQuizId || currentAlternatesRemaining <= 0) return;
    const slotVersion = slotVersions[currentQuestionIndex] || 1;
    if (slotVersion >= 3) return;

    const altBtn = document.getElementById("alternate-question-btn");
    if (!altBtn) return;

    altBtn.disabled = true;
    altBtn.innerHTML = `<span>Generating alternate...</span>`;

    try {
        const response = await fetch(`${AUTH_API}/quiz/alternate`, {
            method: "POST",
            credentials: "include",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                quiz_id: currentQuizId,
                slot_number: currentQuestionIndex + 1
            })
        });

        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || "Could not generate alternate question.");
        }

        // Update active questions array and clear student selection for this slot
        questions[currentQuestionIndex] = data.question;
        selectedAnswers[currentQuestionIndex] = null;
        currentAlternatesRemaining = data.alternates_remaining;
        slotVersions[currentQuestionIndex] = data.version_number;

        renderQuestion();
    } catch (err) {
        console.error("Alternate question error:", err);
        alert(err.message || "Failed to generate alternate question. Please try again.");
    } finally {
        if (altBtn) {
            altBtn.innerHTML = `
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 2v6h-6M3 12a9 9 0 0 1 15-6.7L21 8M3 22v-6h6M21 12a9 9 0 0 1-15 6.7L3 16"/></svg>
                <span>Alternate Question</span>
                <span id="alternate-counter-badge" class="counter-badge">${currentAlternatesRemaining} left</span>
            `;
            updateAlternateButtonUI();
        }
    }
}

const alternateBtnElement = document.getElementById("alternate-question-btn");
if (alternateBtnElement) {
    alternateBtnElement.addEventListener("click", handleAlternateQuestion);
}

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

    updateAlternateButtonUI();
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

        const deepDiveBtn = document.createElement("button");
        deepDiveBtn.type = "button";
        deepDiveBtn.className = "review-deep-dive-btn";
        deepDiveBtn.innerHTML = `<span>💬 Deep Dive with Loomie ✦</span>`;
        deepDiveBtn.addEventListener("click", () => {
            const context = {
                question_number: review.question_number,
                question_text: review.question,
                selected_answer: review.selected_answer_text || review.selected_answer || "None",
                correct_answer: review.correct_answer_text || review.correct_answer,
                explanation: review.explanation,
                topic: document.getElementById("quiz-topic")?.textContent || "Assessment Review"
            };
            openChatDrawer(
                "deep_dive_review",
                context,
                `Can you explain why "${context.correct_answer}" is correct and how this differs from other options?`
            );
        });
        card.appendChild(deepDiveBtn);

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
        const previousEmail = currentUser ? currentUser.email : null;
        currentUser = user;

        // If authenticated user changed, invalidate cached history
        if (previousEmail && previousEmail !== user.email) {
            cachedAssessments = [];
        }

        profileName.textContent = user.name || "Google User";
        profileEmail.textContent = user.email || "";

        if (user.picture) {
            profilePicture.src = user.picture;
            profilePicture.hidden = false;
            profileButton.innerHTML = "";
            const avatarImage = document.createElement("img");
            avatarImage.src = user.picture;
            avatarImage.alt = "Profile";
            avatarImage.className = "avatar-logo-img";
            profileButton.appendChild(avatarImage);
        } else {
            profilePicture.hidden = true;
            profileButton.innerHTML = `<img src="/static/images/logo.png" alt="Profile" class="avatar-logo-img">`;
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
    cachedAssessments = [];
    profileName.textContent = "Guest";
    profileEmail.textContent = "";

    profilePicture.hidden = true;
    profileButton.innerHTML = `<img src="/static/images/logo.png" alt="Profile" class="avatar-logo-img">`;

    const heroAvatar = document.getElementById("profile-hero-avatar");
    if (heroAvatar) {
        heroAvatar.innerHTML = `<img src="/static/images/logo.png" alt="Profile avatar" class="avatar-hero-img">`;
    }

    googleLoginButton.hidden = false;
    logoutButton.hidden = true;

    const welcomeGreeting = document.getElementById("welcome-greeting");
    const welcomeSubtext = document.getElementById("welcome-subtext");
    if (welcomeGreeting) welcomeGreeting.textContent = "Learn something new today.";
    if (welcomeSubtext) welcomeSubtext.textContent = "Practice your knowledge with AI-generated assessments.";

    // Reset metrics
    const totalEl = document.getElementById("total-assessments");
    const completedEl = document.getElementById("completed-assessments");
    const avgEl = document.getElementById("average-score");
    if (totalEl) totalEl.textContent = "0";
    if (completedEl) completedEl.textContent = "0";
    if (avgEl) avgEl.textContent = "—";

    renderRecentAssessmentsTable([]);
    const myHistoryTbody = document.getElementById("my-assessments-history");
    if (myHistoryTbody) {
        myHistoryTbody.innerHTML = `
            <tr>
                <td colspan="7" class="empty-state">
                    Please sign in with Google to view and manage your assessment history.
                </td>
            </tr>
        `;
    }
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
        await loadAssessmentsView();
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
// Loomie AI Tutor & Learning Coach Controller
// ==========================================

const askLoomieFab = document.getElementById("askloomie-fab");
const chatDrawer = document.getElementById("chat-drawer");
const chatOverlay = document.getElementById("chat-overlay");
const chatCloseBtn = document.getElementById("chat-close-btn");
const chatClearBtn = document.getElementById("chat-clear-btn");
const chatModePill = document.getElementById("chat-mode-pill");
const chatContextBanner = document.getElementById("chat-context-banner");
const contextDesc = document.getElementById("context-desc");
const chatDetachContext = document.getElementById("chat-detach-context");
const chatMessages = document.getElementById("chat-messages");
const chatSuggestionChips = document.getElementById("chat-suggestion-chips");
const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
const chatSendBtn = document.getElementById("chat-send-btn");
const chatCharCounter = document.getElementById("chat-char-counter");
const quizHintBtn = document.getElementById("quiz-hint-btn");

let chatHistory = [];
let currentChatMode = "tutor_general";
let currentChatContext = null;
let isGeneratingResponse = false;

function formatMarkdown(text) {
    if (!text) return "";
    let safe = escapeHtml(text);

    // Code blocks: ```lang\ncode\n```
    safe = safe.replace(/```([a-zA-Z0-9_-]*)\n?([\s\S]*?)```/g, (match, lang, code) => {
        return `<pre><code class="language-${lang}">${code.trim()}</code></pre>`;
    });

    // Inline code: `code`
    safe = safe.replace(/`([^`]+)`/g, "<code>$1</code>");

    // Bold: **text**
    safe = safe.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");

    // Bullet points: - item or * item
    safe = safe.replace(/(?:^|\n)[-*]\s+([^\n]+)/g, "\n<li>$1</li>");
    safe = safe.replace(/(<li>[\s\S]*?<\/li>)/g, "<ul>$1</ul>");
    safe = safe.replace(/<\/ul>\s*<ul>/g, "");

    // Paragraph line breaks
    safe = safe.replace(/\n\n+/g, "</p><p>");
    safe = safe.replace(/\n/g, "<br>");

    return `<p>${safe}</p>`;
}

function updateModePill(mode) {
    currentChatMode = mode;
    if (!chatModePill) return;
    chatModePill.className = "mode-pill";
    if (mode === "socratic_hint") {
        chatModePill.classList.add("socratic");
        chatModePill.textContent = "Socratic Hint";
    } else if (mode === "deep_dive_review") {
        chatModePill.classList.add("review");
        chatModePill.textContent = "Review Deep-Dive";
    } else {
        chatModePill.textContent = "Study Coach";
    }
}

function updateContextBanner(context) {
    currentChatContext = context;
    if (!chatContextBanner || !contextDesc) return;
    if (context && (context.question_text || context.topic)) {
        chatContextBanner.hidden = false;
        const qNum = context.question_number ? `Q${context.question_number} · ` : "";
        const topic = context.topic || "Current Session";
        contextDesc.textContent = `${qNum}${topic}`;
    } else {
        chatContextBanner.hidden = true;
    }
}

function renderSuggestionChips(mode) {
    if (!chatSuggestionChips) return;
    chatSuggestionChips.replaceChildren();
    let chips = [];

    if (mode === "socratic_hint") {
        chips = [
            "💡 Give me a hint",
            "What core concept is being tested?",
            "Explain without giving the answer",
            "Give me a real-world analogy"
        ];
    } else if (mode === "deep_dive_review") {
        chips = [
            "Why is the correct answer right?",
            "Show me a code example",
            "What common mistake causes this?",
            "How do I prevent this bug in production?"
        ];
    } else {
        chips = [
            "What should I study today?",
            "How can I improve my score?",
            "Explain Python generators vs lists",
            "Explain SQL indexing best practices"
        ];
    }

    chips.forEach(chipText => {
        const chip = document.createElement("button");
        chip.type = "button";
        chip.className = "chip-btn";
        chip.textContent = chipText;
        chip.addEventListener("click", () => {
            if (!isGeneratingResponse && chatInput) {
                chatInput.value = chipText;
                submitUserMessage();
            }
        });
        chatSuggestionChips.appendChild(chip);
    });
}

function appendChatMessage(role, content) {
    if (!chatMessages) return null;
    const row = document.createElement("div");
    row.className = `chat-msg-row ${role}`;

    if (role === "assistant") {
        const avatar = document.createElement("div");
        avatar.className = "msg-avatar loomie";
        avatar.textContent = "✦";
        row.appendChild(avatar);
    }

    const bubble = document.createElement("div");
    bubble.className = "msg-bubble";
    if (role === "assistant") {
        bubble.innerHTML = formatMarkdown(content);
    } else {
        bubble.textContent = content;
    }

    row.appendChild(bubble);
    chatMessages.appendChild(row);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return row;
}

function showTypingIndicator() {
    if (!chatMessages) return;
    const row = document.createElement("div");
    row.id = "chat-typing-indicator";
    row.className = "chat-msg-row assistant";

    const avatar = document.createElement("div");
    avatar.className = "msg-avatar loomie";
    avatar.textContent = "✦";
    row.appendChild(avatar);

    const bubble = document.createElement("div");
    bubble.className = "msg-bubble";
    bubble.innerHTML = `
        <div class="typing-dots">
            <span class="typing-dot"></span>
            <span class="typing-dot"></span>
            <span class="typing-dot"></span>
        </div>
    `;
    row.appendChild(bubble);
    chatMessages.appendChild(row);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function removeTypingIndicator() {
    const indicator = document.getElementById("chat-typing-indicator");
    if (indicator) indicator.remove();
}

function openChatDrawer(mode = "tutor_general", context = null, initialPrompt = null) {
    if (!chatDrawer || !chatOverlay) return;
    chatDrawer.hidden = false;
    chatOverlay.hidden = false;

    updateModePill(mode);
    updateContextBanner(context);
    renderSuggestionChips(mode);

    if (chatMessages && chatMessages.children.length === 0) {
        let greeting = "Hello! I'm Loomie, your Askloom AI Learning Coach. Ask me questions about programming, request study recommendations, or get hints on your quizzes!";
        if (mode === "socratic_hint") {
            greeting = "Ready to tackle this question! I won't spoil the answer, but ask me for a hint, a conceptual clue, or code tracing help whenever you're stuck.";
        } else if (mode === "deep_dive_review") {
            greeting = "Let's review this question together! Ask me why the correct choice works, what makes other options suboptimal, or request a concrete code example.";
        }
        appendChatMessage("assistant", greeting);
    }

    if (chatInput) {
        chatInput.focus();
        if (initialPrompt && !isGeneratingResponse) {
            chatInput.value = initialPrompt;
            submitUserMessage();
        }
    }
}

function closeChatDrawer() {
    if (chatDrawer) chatDrawer.hidden = true;
    if (chatOverlay) chatOverlay.hidden = true;
}

function clearChatHistory() {
    chatHistory = [];
    if (!chatMessages) return;
    chatMessages.replaceChildren();
    let greeting = "Conversation cleared. How can I help you today?";
    if (currentChatMode === "socratic_hint") {
        greeting = "Conversation reset. What conceptual hint can I provide for this question?";
    } else if (currentChatMode === "deep_dive_review") {
        greeting = "Conversation reset. What aspect of this question would you like to explore?";
    }
    appendChatMessage("assistant", greeting);
}

async function submitUserMessage() {
    if (!chatInput) return;
    const text = (chatInput.value || "").trim();
    if (!text || isGeneratingResponse) return;

    chatInput.value = "";
    if (chatCharCounter) chatCharCounter.textContent = "0 / 1000";
    chatInput.style.height = "auto";
    if (chatSendBtn) chatSendBtn.disabled = true;

    appendChatMessage("user", text);
    chatHistory.push({ role: "user", content: text });

    isGeneratingResponse = true;
    showTypingIndicator();

    try {
        const payload = {
            message: text,
            mode: currentChatMode,
            context: currentChatContext || {},
            history: chatHistory.slice(-6)
        };

        const response = await fetch(`${AUTH_API}/chat/message`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify(payload)
        });

        removeTypingIndicator();

        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.detail || "Loomie could not generate a response.");
        }

        const data = await response.json();
        appendChatMessage("assistant", data.reply);
        chatHistory.push({ role: "assistant", content: data.reply });

    } catch (error) {
        removeTypingIndicator();
        appendChatMessage("assistant", `⚠️ ${error.message || "An unexpected error occurred. Please try again."}`);
    } finally {
        isGeneratingResponse = false;
        if (chatSendBtn && chatInput) {
            chatSendBtn.disabled = !chatInput.value.trim();
        }
        if (chatInput) chatInput.focus();
    }
}

// Event Listeners for Loomie AI Tutor
if (askLoomieFab) {
    askLoomieFab.addEventListener("click", () => {
        openChatDrawer("tutor_general");
    });
}

if (chatCloseBtn) {
    chatCloseBtn.addEventListener("click", closeChatDrawer);
}

if (chatOverlay) {
    chatOverlay.addEventListener("click", closeChatDrawer);
}

if (chatClearBtn) {
    chatClearBtn.addEventListener("click", clearChatHistory);
}

if (chatDetachContext) {
    chatDetachContext.addEventListener("click", () => {
        updateContextBanner(null);
        updateModePill("tutor_general");
        renderSuggestionChips("tutor_general");
    });
}

if (quizHintBtn) {
    quizHintBtn.addEventListener("click", () => {
        const q = questions[currentQuestionIndex];
        const topicEl = document.getElementById("quiz-topic");
        const diffEl = document.getElementById("difficulty");
        const context = {
            question_number: currentQuestionIndex + 1,
            question_text: q ? q.question : "",
            options: q ? q.options : [],
            topic: topicEl ? topicEl.textContent : "Current Assessment",
            difficulty: diffEl ? diffEl.value : "Medium"
        };
        openChatDrawer(
            "socratic_hint",
            context,
            "Can you give me a Socratic hint for this question without spoiling the answer?"
        );
    });
}

if (chatInput) {
    chatInput.addEventListener("input", () => {
        chatInput.style.height = "auto";
        chatInput.style.height = Math.min(chatInput.scrollHeight, 120) + "px";
        const len = chatInput.value.length;
        if (chatCharCounter) chatCharCounter.textContent = `${len} / 1000`;
        if (chatSendBtn) chatSendBtn.disabled = len === 0 || isGeneratingResponse;
    });

    chatInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            submitUserMessage();
        }
    });
}

if (chatForm) {
    chatForm.addEventListener("submit", (e) => {
        e.preventDefault();
        submitUserMessage();
    });
}

// ==========================================
// Global Window Exports
// ==========================================

window.navigateToView = navigateToView;
window.showQuizSetup = showQuizSetup;
window.cancelQuizSetup = cancelQuizSetup;
window.openPastQuizReview = openPastQuizReview;
window.openChatDrawer = openChatDrawer;
window.closeChatDrawer = closeChatDrawer;

// Initialize session and route
loadUserProfile();
initRouter();
