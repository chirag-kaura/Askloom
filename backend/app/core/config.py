# Askloom starter file: backend/app/core/config.py


import os
from pathlib import Path

from dotenv import load_dotenv

# Load backend/.env regardless of the terminal's current directory
BACKEND_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BACKEND_DIR / ".env"

load_dotenv(ENV_FILE)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

