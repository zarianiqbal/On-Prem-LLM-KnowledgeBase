"""User management routes (admin only).

Since Google login creates users with no roles, admins use these endpoints to
assign roles and grant/revoke admin. A user with no roles is treated as a
`customer` (least privilege) by the retrieval layer.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import auth
from app.database import get_db
from app.models import User
from app.schemas import UserAdminOut, UserUpdate

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=list[UserAdminOut])
def list_users(
    _: auth.CurrentUser = Depends(auth.require_admin),
    db: Session = Depends(get_db),
):
    return db.query(User).order_by(User.created_at).all()


@router.patch("/{user_id}", response_model=UserAdminOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    current: auth.CurrentUser = Depends(auth.require_admin),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    # Prevent an admin from accidentally locking everyone out by demoting the
    # last remaining admin (including themselves).
    if user.is_admin and not payload.is_admin:
        remaining_admins = db.query(User).filter(User.is_admin.is_(True)).count()
        if remaining_admins <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot remove the last admin.",
            )
    user.roles = [r.strip() for r in payload.roles if r.strip()]
    user.is_admin = payload.is_admin
    db.commit()
    db.refresh(user)
    return user
