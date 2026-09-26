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
    """The one place a notification actually gets written — called as a
    side effect from services/users.py (user created) and
    services/invoices.py (invoice generated/accepted/rejected). Not
    validated against who user_id/related_* actually are beyond the real
    FK constraints already on the table — every call site here passes ids
    it already knows are valid (the creating vendor, the invoice's own
    assignee/project vendor)."""
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
    """Unread means unread, not un-seen — readAt is the meaningful state
    for "do I need to look at this," seenAt is the lighter-weight one."""
    return db.execute(
        select(Notification)
        .where(Notification.userId == user_id, Notification.readAt.is_(None))
        .order_by(Notification.createdAt.desc())
    ).scalars().all()


def get_notification_by_id(db: Session, notification_id) -> Notification | None:
    return db.get(Notification, notification_id)


def mark_seen(db: Session, notification: Notification) -> Notification:
    """Takes the already-fetched, already-ownership-checked notification
    (not an id) — the route layer is responsible for the 404/403 checks
    before calling this, so this function only ever mutates, never
    authorizes."""
    if notification.seenAt is None:
        notification.seenAt = datetime.now(timezone.utc)
        db.commit()
        db.refresh(notification)
    return notification


def mark_read(db: Session, notification: Notification) -> Notification:
    """Reading implies having seen it — sets seenAt too, if it wasn't
    already set, rather than leaving a read-but-technically-never-seen row."""
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
