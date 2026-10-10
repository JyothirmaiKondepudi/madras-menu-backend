from sqlalchemy import Column, String, DateTime, ForeignKey, func, Index, text
from sqlalchemy.dialects.postgresql import UUID
import uuid
from database import Base


class Notification(Base):
    """One row per notification event. type is a plain string, not a Postgres
    enum, so new event types don't need a migration. seenAt (showed up in the
    feed) and readAt (explicitly acknowledged) are separate, nullable states."""

    __tablename__ = "notifications"
    __table_args__ = (
        Index(
            "notifications_unread_by_user",
            "user_id",
            "created_at",
            postgresql_where=text("read_at IS NULL"),
        ),
    )

    # CASCADE on every FK: a notification shouldn't block deleting the
    # invoice/user it references.
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    userId = Column(
        "user_id",
        UUID(as_uuid=True),
        ForeignKey("user_data.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type = Column("type", String, nullable=False)
    message = Column("message", String, nullable=False)
    # At most one of these is set per notification (invoice events set
    # relatedInvoiceId, user-created events set relatedUserId).
    relatedInvoiceId = Column(
        "related_invoice_id",
        UUID(as_uuid=True),
        ForeignKey("invoices.invoice_id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    relatedUserId = Column(
        "related_user_id",
        UUID(as_uuid=True),
        ForeignKey("user_data.user_id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    seenAt = Column("seen_at", DateTime(timezone=True), nullable=True)
    readAt = Column("read_at", DateTime(timezone=True), nullable=True)
    createdAt = Column(
        "created_at", DateTime(timezone=True), server_default=func.now(), nullable=False
    )
