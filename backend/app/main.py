
import os

from authlib.integrations.starlette_client import OAuth
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from backend.app.api.routes import router as quiz_router
from backend.app.core import config
from backend.app.db.database import get_db
from backend.app.models import User

app = FastAPI(
    title="Askloom API",
    description="Backend API for the Askloom AI-powered quiz application.",
    version="0.1.0",
)

DB_DEPENDENCY = Depends(get_db)

# Google OAuth configuration
oauth = OAuth()

oauth.register(
    name="google",
    client_id=config.GOOGLE_CLIENT_ID,
    client_secret=config.GOOGLE_CLIENT_SECRET,
    server_metadata_url=(
        "https://accounts.google.com/.well-known/openid-configuration"
    ),
    client_kwargs={"scope": "openid email profile"},
)

# Session configuration
app.add_middleware(
    SessionMiddleware,
    secret_key=config.SESSION_SECRET,
    same_site="lax",
    https_only=os.getenv("SESSION_HTTPS_ONLY", "false").lower() == "true",
)

# Allow local development and the deployed frontend
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


@app.get("/auth/google/login", tags=["Authentication"])
async def google_login(request: Request):
    """Redirect the user to Google for authentication."""
    redirect_uri = request.url_for("google_callback")
    return await oauth.google.authorize_redirect(request, redirect_uri)


@app.get(
    "/auth/google/callback",
    name="google_callback",
    tags=["Authentication"],
)
async def google_callback(
    request: Request,
    db: Session = DB_DEPENDENCY,
    
):
    """Handle Google OAuth and synchronize the user with PostgreSQL."""
    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"OAuth authorization failed: {exc!s}",
        ) from exc

    google_user = token.get("userinfo")

    if not google_user:
        raise HTTPException(
            status_code=400,
            detail="Unable to retrieve Google user information.",
        )

    email = google_user.get("email")

    if not email or not google_user.get("email_verified"):
        raise HTTPException(
            status_code=400,
            detail="A verified Google email address is required.",
        )

    db_user = db.scalar(select(User).where(User.email == email))

    if db_user is None:
        db_user = User(email=email)
        db.add(db_user)

        try:
            db.commit()
            db.refresh(db_user)
        except IntegrityError:
            db.rollback()
            db_user = db.scalar(select(User).where(User.email == email))

            if db_user is None:
                raise HTTPException(
                    status_code=500,
                    detail="Could not create or retrieve the user account.",
                )

    request.session["user"] = {
        "user_id": db_user.user_id,
        "google_id": google_user.get("sub"),
        "name": google_user.get("name"),
        "email": db_user.email,
        "picture": google_user.get("picture"),
    }

    frontend_url = os.getenv(
        "FRONTEND_URL",
        "http://127.0.0.1:5000",
    ).split(",")[0].strip().rstrip("/")

    return RedirectResponse(
        url=f"{frontend_url}/",
        status_code=302,
    )


@app.post("/auth/logout", tags=["Authentication"])
async def logout(request: Request):
    """Log out the current user by clearing their session."""
    request.session.clear()
    return {"message": "Logged out successfully"}


@app.get("/auth/me", tags=["Authentication"])
def get_current_user(
    request: Request,
    db: Session = DB_DEPENDENCY,
):
    """Return the currently authenticated user's profile."""
    user = request.session.get("user")

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
        )

    user_data = dict(user)

    if "user_id" in user_data:
        db_user = db.get(User, user_data["user_id"])
        if db_user and db_user.created_at:
            user_data["created_at"] = db_user.created_at.isoformat()

    return {"user": user_data}


@app.get("/health", tags=["Health"])
def health_check():
    """Check whether the Askloom API is running."""
    return {
        "status": "healthy",
        "application": "Askloom",
    }
