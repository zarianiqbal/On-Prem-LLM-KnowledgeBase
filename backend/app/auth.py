"""Authentication: JWT issuance/verification and the current-user dependency.

The JWT carries the user's email and roles. Every protected request extracts
those roles and passes them to the retrieval layer for ACL filtering, so the
LLM only ever sees chunks the requesting user is allowed to see.

Dev mode (`DEV_AUTH_ENABLED=true`) lets you log in by simply choosing a role —
no Google account required — so you can build and test locally. Swap in real
Google OAuth for production (see `login_google` stub below).
"""
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User

bearer_scheme = HTTPBearer(auto_error=False)


class CurrentUser(BaseModel):
    email: str
    name: str
    roles: list[str]
    is_admin: bool


def create_access_token(user: User) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub": user.email,
        "name": user.name,
        "roles": user.roles,
        "is_admin": user.is_admin,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def upsert_user(
    db: Session, email: str, name: str, roles: list[str], is_admin: bool
) -> User:
    """Create the user if new, otherwise update their profile/roles."""
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        user = User(email=email, name=name, roles=roles, is_admin=is_admin)
        db.add(user)
    else:
        user.name = name or user.name
        user.roles = roles
        user.is_admin = is_admin
    db.commit()
    db.refresh(user)
    return user


def get_or_create_oauth_user(db: Session, email: str, name: str) -> User:
    """Log a Google user in without clobbering admin-assigned roles.

    New users start with NO roles and non-admin (an admin assigns roles later),
    except emails in ADMIN_EMAILS, which are bootstrapped as admins so there's
    always a way in on a fresh install. Existing users keep their roles; we only
    refresh their display name and ensure configured admins stay admins.
    """
    email = email.lower()
    is_bootstrap_admin = email in settings.admin_email_list
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        user = User(email=email, name=name, roles=[], is_admin=is_bootstrap_admin)
        db.add(user)
    else:
        user.name = name or user.name
        if is_bootstrap_admin:
            user.is_admin = True
    db.commit()
    db.refresh(user)
    return user


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> CurrentUser:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return CurrentUser(
        email=payload.get("sub", ""),
        name=payload.get("name", ""),
        roles=payload.get("roles", []) or [],
        is_admin=payload.get("is_admin", False),
    )


def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required"
        )
    return user
