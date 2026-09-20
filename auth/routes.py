from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import User
from schemas.user import UserOut
from auth.schema import LoginRequest, TokenResponse, ChangePasswordRequest
from auth.service import authenticate_user, change_password
from auth.security import create_access_token
from auth.dependencies import get_current_user

router = APIRouter()


@router.post("/auth/login", response_model=TokenResponse)
def login(credentials: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_user(credentials.email, credentials.password, db)
    if user is None:
        # Same message whether the email doesn't exist or the password was
        # wrong — a specific message either way would tell a caller which
        # emails have accounts.
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token(user.userId)
    return TokenResponse(access_token=token)


@router.get("/auth/me", response_model=UserOut)
def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/auth/change-password", status_code=204)
def change_password_route(
    body: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # self-service only, by design — this changes the authenticated
    # caller's own password and nobody else's, and requires proving the
    # current one. An admin-reset-someone-else's-password path is a
    # separate, deliberately not-yet-built capability.
    if not change_password(current_user, body.currentPassword, body.newPassword, db):
        raise HTTPException(status_code=401, detail="Current password is incorrect")


@router.patch("/auth/clear-notification", status_code=204)
def clear_notification(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Self-service only — a user acknowledges their own notification flag,
    e.g. after opening their dashboard. Nobody clears someone else's."""
    current_user.hasNotification = False
    db.commit()
