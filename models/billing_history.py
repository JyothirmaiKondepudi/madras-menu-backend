from sqlalchemy import (
    Column,
    String,
    DateTime,
    Integer,
    Enum,
    ForeignKey,
    ARRAY,
    Numeric,
    func,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import uuid
from database import Base


class BillingHistory(Base):
    __tablename__ = "billing_history"

    # Per-transaction id; one invoice can have many rows (payment, refund, ...).
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoiceId = Column(
        "invoice_id",
        UUID(as_uuid=True),
        ForeignKey("invoices.invoice_id"),
        index=True,
        nullable=False,
    )
    # Plain string, not an enum, so new Stripe event types don't need a migration.
    eventType = Column("event_type", String, nullable=False)
    # dollars, same unit as invoices (was integer cents)
    amount = Column("amount", Numeric(12, 2), nullable=False)
    occurredAt = Column("occurred_at", DateTime(timezone=True), server_default=func.now(), nullable=True)
    source = Column(
        "source", Enum("Manual", "Stripe", name="source_enum"), nullable=False
    )
    failureReason = Column("failure_reason", String, nullable=True)
    # "metadata" is reserved by SQLAlchemy.
    billingMetadata = Column("metadata", JSONB)
