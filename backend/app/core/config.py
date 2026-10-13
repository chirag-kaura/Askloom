# Askloom starter file: backend/app/core/config.py


import os
from pathlib import Path

from dotenv import load_dotenv

# Load backend/.env regardless of the terminal's current directory
BACKEND_DIR = Path(__file__).resolve().parents[3]
ENV_FILE = BACKEND_DIR / ".env"

load_dotenv(ENV_FILE)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

# Google OAuth settings
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

# Session security
SESSION_SECRET = os.getenv("SESSION_SECRET")