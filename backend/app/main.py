
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.routes import router as quiz_router

app = FastAPI(
    title="Askloom API",
    description="Backend API for the Askloom AI-powered quiz application.",
    version="0.1.0",
)

oauth = OAuth()

oauth.register(
    name="google",
    client_id=config.GOOGLE_CLIENT_ID,
    client_secret=config.GOOGLE_CLIENT_SECRET,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={
        "scope": "openid email profile",
    },
)

app.add_middleware(
    SessionMiddleware,
    secret_key=config.SESSION_SECRET,
    same_site="lax",
    https_only=False,  # Local development only
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5000"],
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
