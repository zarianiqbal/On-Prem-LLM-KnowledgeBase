"""Auth routes: dev login (role-based) and Google OAuth (login + callback)."""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app import auth
from app.config import settings
from app.database import get_db
from app.oauth import oauth
from app.schemas import AuthConfig, DevLoginRequest, TokenResponse, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/dev-login", response_model=TokenResponse)
def dev_login(payload: DevLoginRequest, db: Session = Depends(get_db)):
    """Log in by choosing an email + roles. For local development only.

    Disabled when DEV_AUTH_ENABLED=false so it can't leak into production.
    """
    if not settings.dev_auth_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Dev auth is disabled. Use Google OAuth.",
        )
    user = auth.upsert_user(
        db,
        email=payload.email,
        name=payload.name,
        roles=payload.roles,
        is_admin=payload.is_admin,
    )
    return TokenResponse(access_token=auth.create_access_token(user))


@router.get("/me", response_model=UserOut)
def me(current: auth.CurrentUser = Depends(auth.get_current_user)):
    return UserOut(
        email=current.email,
        name=current.name,
        roles=current.roles,
        is_admin=current.is_admin,
    )


@router.get("/config", response_model=AuthConfig)
def auth_config():
    """Lets the frontend know which login methods to show."""
    return AuthConfig(
        google_enabled=settings.google_oauth_enabled,
        dev_login_enabled=settings.dev_auth_enabled,
    )


# --- Google OAuth -------------------------------------------------------------
# Simple MVP flow: sign in with Google (email + name only). New users arrive with
# no roles; an admin assigns roles from the Admin page. Emails in ADMIN_EMAILS are
# auto-promoted to admin so a fresh install always has a way in.
@router.get("/google/login")
async def google_login(request: Request):
    if not settings.google_oauth_enabled:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Google OAuth not configured. Set GOOGLE_CLIENT_ID/SECRET.",
        )
    return await oauth.google.authorize_redirect(
        request, settings.google_redirect_uri
    )


@router.get("/google/callback")
async def google_callback(request: Request, db: Session = Depends(get_db)):
    if not settings.google_oauth_enabled:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Google OAuth not configured.",
        )
    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception:
        # Redirect back to the login page with an error flag rather than 500.
        return RedirectResponse(url=f"{settings.frontend_origin}/login#error=oauth")

    userinfo = token.get("userinfo") or {}
    email = userinfo.get("email")
    if not email:
        return RedirectResponse(url=f"{settings.frontend_origin}/login#error=email")

    user = auth.get_or_create_oauth_user(db, email=email, name=userinfo.get("name", ""))
    jwt_token = auth.create_access_token(user)
    # Pass the token in the URL fragment (#) so it never reaches any server log.
    return RedirectResponse(url=f"{settings.frontend_origin}/login#token={jwt_token}")
