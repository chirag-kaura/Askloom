
"""
Askloom Project Scaffolding Script

Creates the initial project structure and starter files for Askloom.
Existing files are preserved by default.
"""

from pathlib import Path

# ============================================================
# 1. PROJECT ROOT
# ============================================================

ROOT_DIR = Path(__file__).resolve().parent


# ============================================================
# 2. PROJECT DIRECTORY STRUCTURE
# ============================================================

PROJECT_STRUCTURE = [
    "frontend/templates",
    "frontend/static/css",
    "frontend/static/js",
    "backend/app/core",
    "backend/app/api",
    "backend/app/schemas",
    "backend/app/services",
    "backend/app/db",
    "backend/tests",
    "docs",
    ".github/workflows",
]


# ============================================================
# 3. STARTER FILE CONTENTS
# ============================================================

FILE_CONTENTS = {
    # Frontend: Flask
    "frontend/app.py": '''"""Askloom Flask frontend application."""\n''',

    "frontend/templates/index.html": """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Askloom</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
</head>
<body>
    <main>
        <h1>Welcome to Askloom</h1>
        <p>Your AI-powered quiz experience starts here.</p>
    </main>
    <script src="{{ url_for('static', filename='js/app.js') }}"></script>
</body>
</html>
""",

    "frontend/static/css/style.css": """/* Askloom frontend styles */

body {
    font-family: Arial, sans-serif;
    margin: 0;
    padding: 2rem;
}
""",

    "frontend/static/js/app.js": """// Askloom frontend scripts

console.log("Askloom frontend loaded.");
""",

    # Backend: FastAPI
    "backend/app/main.py": '''"""Askloom FastAPI backend application."""\n''',

    "backend/app/core/config.py": '''"""Application configuration."""\n''',

    "backend/app/api/routes.py": '''"""FastAPI route definitions."""\n''',

    "backend/app/schemas/question.py": '''"""Pydantic schemas for quiz questions."""\n''',

    "backend/app/services/llm_service.py": '''"""LLM question-generation service."""\n''',

    "backend/app/db/database.py": '''"""PostgreSQL database connection setup."""\n''',

    # Tests
    "backend/tests/test_health.py": '''"""Tests for the FastAPI health endpoint."""\n''',

    # Documentation
    "docs/REQUIREMENTS.md": """# Askloom Requirements

Project requirements and implementation decisions will be documented here.
""",

    # Environment configuration
    ".env.example": """# Copy to .env and provide your own values.
# Never commit real API keys or passwords.

GROQ_API_KEY=
DATABASE_URL=
""",

    # Docker
    "Dockerfile": """# Askloom container configuration
# Container setup will be added after application implementation.
""",

    "docker-compose.yml": """# Askloom local development services
# Service definitions will be added in a later step.
""",

    # Dependencies
    "requirements.txt": """# Askloom Python dependencies
# Exact dependencies will be added after the application structure is finalized.
""",

    # GitHub Actions
    ".github/workflows/tests.yml": """# Askloom automated testing workflow
# CI configuration will be added in a later step.
""",
}


# ============================================================
# 4. CREATE DIRECTORIES
# ============================================================

def create_directories():
    """Create the required project directories."""
    for folder in PROJECT_STRUCTURE:
        folder_path = ROOT_DIR / folder
        folder_path.mkdir(parents=True, exist_ok=True)

    print("Project directories checked successfully.")


# ============================================================
# 5. CREATE STARTER FILES
# ============================================================

def create_starter_files():
    """Create starter files without overwriting existing files."""
    created_count = 0
    skipped_count = 0

    for file_name, content in FILE_CONTENTS.items():
        file_path = ROOT_DIR / file_name

        if file_path.exists():
            skipped_count += 1
            print(f"Skipped existing file: {file_name}")
            continue

        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")

        created_count += 1
        print(f"Created: {file_name}")

    print("\nStarter-file creation complete.")
    print(f"Created: {created_count}")
    print(f"Skipped existing: {skipped_count}")


# ============================================================
# 6. MAIN EXECUTION
# ============================================================

def main():
    """Run the Askloom scaffolding process."""
    print("Starting Askloom project scaffolding...\n")

    create_directories()
    create_starter_files()

    print("\nAskloom scaffolding finished successfully.")


if __name__ == "__main__":
    main()
