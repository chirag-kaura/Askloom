import logging
import os

from authlib.integrations.starlette_client import OAuth
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from backend.app.api.chat import router as chat_router
from backend.app.api.routes import router as quiz_router
from backend.app.core import config
from backend.app.db.database import get_db
from backend.app.models import User

logger = logging.getLogger("askloom")

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

# Detect production environment (Render or HTTPS frontend origins)
is_production = bool(
    os.getenv("RENDER")
    or os.getenv("SESSION_HTTPS_ONLY", "").lower() == "true"
    or any("https://" in origin for origin in allowed_origins)
)

# Cross-origin cookies between frontend (e.g., onrender.com) and backend require SameSite=None and Secure=True
app.add_middleware(
    SessionMiddleware,
    secret_key=config.SESSION_SECRET,
    same_site="none" if is_production else "lax",
    https_only=is_production,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Trust reverse-proxy headers from Render / load balancers for correct scheme (HTTPS) and host
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")

app.include_router(quiz_router)
app.include_router(chat_router)


@app.get("/", tags=["Health"])
def root():
    """Service status and API entrypoint."""
    return {
        "status": "healthy",
        "service": "Askloom API",
        "version": "0.1.0",
        "docs": "/docs",
    }


@app.get("/auth/google/login", tags=["Authentication"])
async def google_login(request: Request):
    """Redirect the user to Google for authentication."""
    redirect_uri = str(request.url_for("google_callback"))
    # In production or behind an HTTPS proxy, ensure https scheme
    if request.headers.get("x-forwarded-proto") == "https" or "onrender.com" in str(request.base_url):
        redirect_uri = redirect_uri.replace("http://", "https://", 1)

    return await oauth.google.authorize_redirect(
        request,
        redirect_uri,
        prompt="select_account",
    )


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
        logger.error("OAuth authorize_access_token failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=400,
            detail=f"OAuth authorization failed: {exc!s}",
        ) from exc

    google_user = token.get("userinfo")
    if not google_user:
        try:
            google_user = await oauth.google.userinfo(token=token)
        except Exception as exc:
            logger.warning("oauth.google.userinfo fallback failed: %s", exc)
            google_user = None

    if not google_user:
        raise HTTPException(
            status_code=400,
            detail="Unable to retrieve Google user information.",
        )

    raw_email = google_user.get("email")

    if not raw_email or not google_user.get("email_verified"):
        raise HTTPException(
            status_code=400,
            detail="A verified Google email address is required.",
        )

    email = raw_email.strip().lower()

    try:
        # Find the existing database account by its unique email.
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
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Database error during Google callback: %s", exc, exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Database synchronization failed: {exc!s}",
        ) from exc

    # Clean existing session before setting the new user to prevent cross-account bleeding
    request.session.clear()

    # Store the database ID alongside the Google profile in the session.
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
        url=f"{frontend_url}/dashboard",
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
