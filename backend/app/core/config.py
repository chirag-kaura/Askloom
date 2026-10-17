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

GROQ_API_KEY = (os.getenv("GROQ_API_KEY") or "").strip()
DATABASE_URL = (os.getenv("DATABASE_URL") or "").strip()

# Google OAuth settings
GOOGLE_CLIENT_ID = (os.getenv("GOOGLE_CLIENT_ID") or "").strip()
GOOGLE_CLIENT_SECRET = (os.getenv("GOOGLE_CLIENT_SECRET") or "").strip()

# Session security
SESSION_SECRET = (os.getenv("SESSION_SECRET") or "").strip()