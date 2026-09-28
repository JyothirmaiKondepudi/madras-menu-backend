from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.notifications import Notification


def create_notification(
    db: Session,
    user_id,
    type: str,
    message: str,
    related_invoice_id=None,
    related_user_id=None,
) -> Notification:
    """The one place a notification gets written, called as a side effect from
    services/users.py and services/invoices.py. Trusts callers to pass valid ids;
    relies on the table's FK constraints, not extra validation here."""
    notification = Notification(
        userId=user_id,
        type=type,
        message=message,
        relatedInvoiceId=related_invoice_id,
        relatedUserId=related_user_id,
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification


def get_unread_notifications(db: Session, user_id):
    """Unread, not un-seen: filters on readAt, not seenAt."""
    return db.execute(
        select(Notification)
        .where(Notification.userId == user_id, Notification.readAt.is_(None))
        .order_by(Notification.createdAt.desc())
    ).scalars().all()


def get_notification_by_id(db: Session, notification_id) -> Notification | None:
    return db.get(Notification, notification_id)


def mark_seen(db: Session, notification: Notification) -> Notification:
    """Takes an already-fetched, already-authorized notification — the route
    layer handles 404/403 checks; this only mutates."""
    if notification.seenAt is None:
        notification.seenAt = datetime.now(timezone.utc)
        db.commit()
        db.refresh(notification)
    return notification


def mark_read(db: Session, notification: Notification) -> Notification:
    """Reading implies seeing it, so this sets seenAt too if not already set."""
    changed = False
    now = datetime.now(timezone.utc)
    if notification.seenAt is None:
        notification.seenAt = now
        changed = True
    if notification.readAt is None:
        notification.readAt = now
        changed = True
    if changed:
        db.commit()
        db.refresh(notification)
    return notification
