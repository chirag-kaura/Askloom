# Askloom starter file: backend/app/core/config.py


import os
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

# Load .env from project root or find_dotenv
BACKEND_DIR = Path(__file__).resolve().parents[3]
ENV_FILE = BACKEND_DIR / ".env"

if ENV_FILE.exists():
    load_dotenv(ENV_FILE)
else:
    load_dotenv(find_dotenv())


def _clean_env(key: str, default: str = "") -> str:
    raw = os.getenv(key, default)
    if not raw:
        return ""
    return raw.strip().strip('"').strip("'")


GROQ_API_KEY = _clean_env("GROQ_API_KEY")
DATABASE_URL = _clean_env("DATABASE_URL")

# Google OAuth settings
GOOGLE_CLIENT_ID = _clean_env("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = _clean_env("GOOGLE_CLIENT_SECRET")

# Session security
SESSION_SECRET = _clean_env("SESSION_SECRET")
