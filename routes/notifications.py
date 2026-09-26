from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import User
from auth.dependencies import get_current_user
from schemas.notification import NotificationOut
from services.notifications import get_unread_notifications, get_notification_by_id, mark_seen, mark_read

router = APIRouter()

# Every route here is self-service only, scoped by identity — a
# notification belongs to exactly one user, and nobody (not even an
# vendor) reads or acknowledges someone else's on their behalf. No
# permission required beyond being logged in.


@router.get("/notifications/unread", response_model=list[NotificationOut])
def list_unread_notifications(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return get_unread_notifications(db, current_user.userId)


@router.patch("/notifications/{notification_id}/seen", response_model=NotificationOut)
def mark_notification_seen(
    notification_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    notification = get_notification_by_id(db, notification_id)
    if notification is None:
        raise HTTPException(status_code=404, detail="notification not found")
    if notification.userId != current_user.userId:
        raise HTTPException(status_code=403, detail="not authorized to modify this notification")
    return mark_seen(db, notification)


@router.patch("/notifications/{notification_id}/read", response_model=NotificationOut)
def mark_notification_read(
    notification_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    notification = get_notification_by_id(db, notification_id)
    if notification is None:
        raise HTTPException(status_code=404, detail="notification not found")
    if notification.userId != current_user.userId:
        raise HTTPException(status_code=403, detail="not authorized to modify this notification")
    return mark_read(db, notification)
