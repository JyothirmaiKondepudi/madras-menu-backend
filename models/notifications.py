from sqlalchemy import Column, String, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
import uuid
from database import Base


class Notification(Base):
    """One row per notification event — not a boolean flag, since a user
    can have several independent notifications, each with its own
    read/seen state. type is a plain string (not a Postgres enum) on
    purpose: adding a new event type shouldn't require an ALTER TYPE
    migration the way invoices.invoice_status_enum did.

    seenAt vs. readAt are genuinely distinct states: seen means it showed
    up in the user's feed, read means they explicitly acknowledged it.
    Both nullable — null means "hasn't happened yet.\""""
    __tablename__ = 'notifications'

    # ondelete="CASCADE" on every FK here, deliberately: a notification is
    # an ephemeral, derived record, not something that should ever block
    # deleting the invoice/user it's about (or the user it's for). Caught
    # for real: deleting an invoice/user failed with a 409 the moment a
    # notification referenced it, before these were added.
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    userId = Column(
        "user_id", UUID(as_uuid=True), ForeignKey('user_data.user_id', ondelete="CASCADE"), nullable=False
    )
    type = Column("type", String, nullable=False)
    message = Column("message", String, nullable=False)
    # Optional references to what this notification is about — at most one
    # of these is set per notification today (invoice events set
    # relatedInvoiceId, user-created events set relatedUserId).
    relatedInvoiceId = Column(
        "related_invoice_id", UUID(as_uuid=True), ForeignKey('invoices.invoice_id', ondelete="CASCADE"), nullable=True
    )
    relatedUserId = Column(
        "related_user_id", UUID(as_uuid=True), ForeignKey('user_data.user_id', ondelete="CASCADE"), nullable=True
    )
    seenAt = Column("seen_at", DateTime(timezone=True), nullable=True)
    readAt = Column("read_at", DateTime(timezone=True), nullable=True)
    createdAt = Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False)
