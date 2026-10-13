
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from backend.app.api.routes import router as quiz_router
from backend.app.core import config
from authlib.integrations.starlette_client import OAuth

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


from fastapi import Request
from fastapi.responses import RedirectResponse


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
async def google_callback(request: Request):
    """Handle Google's OAuth callback."""
    token = await oauth.google.authorize_access_token(request)

    user = token.get("userinfo")

    if not user:
        return {
            "error": "Unable to retrieve Google user information."
        }

    # Store the authenticated user's basic details in the session.
    request.session["user"] = {
        "google_id": user.get("sub"),
        "name": user.get("name"),
        "email": user.get("email"),
        "picture": user.get("picture"),
    }

    return {
        "message": "Google login successful",
        "user": request.session["user"],
    }


@app.post("/auth/logout", tags=["Authentication"])
async def logout(request: Request):
    """Log out the current user by clearing their session."""
    request.session.clear()
    return {"message": "Logged out successfully"}


@app.get("/auth/me", tags=["Authentication"])
async def get_current_user(request: Request):
    """Return the currently authenticated user's profile."""
    user = request.session.get("user")

    if not user:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
        )

    return {"user": user}


@app.get("/health", tags=["Health"])
def health_check():
    """Check whether the Askloom API is running."""
    return {
        "status": "healthy",
        "application": "Askloom",
    }
