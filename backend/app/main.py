
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.routes import router as quiz_router

app = FastAPI(
    title="Askloom API",
    description="Backend API for the Askloom AI-powered quiz application.",
    version="0.1.0",
)

# Local development and deployed frontend URLs
frontend_urls = os.getenv(
    "FRONTEND_URL",
    "http://127.0.0.1:5000,http://localhost:5000",
)

allowed_origins = [
    url.strip().rstrip("/")
    for url in frontend_urls.split(",")
    if url.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(quiz_router)


@app.get("/health", tags=["Health"])
def health_check():
    """Check whether the Askloom API is running."""
    return {
        "status": "healthy",
        "application": "Askloom",
    }
