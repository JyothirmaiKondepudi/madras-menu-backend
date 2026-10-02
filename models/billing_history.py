from sqlalchemy import Column, String, DateTime, Float, Integer, Enum, ForeignKey, ARRAY
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
from database import Base


class BillingHistory(Base):
    __tablename__ = 'billing_history'

    # This table's own row id — the "payment id" for each individual
    # transaction. invoiceId is deliberately NOT the primary key: a single
    # invoice can have many billing_history rows (a payment, then a later
    # refund, a declined attempt, etc.), so it has to be a plain FK.
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoiceId = Column('invoice_id', UUID(as_uuid=True), ForeignKey('invoices.invoice_id'), nullable=False)
    # Plain string, not a Postgres enum — new Stripe event types will show
    # up constantly, and a DB enum means an ALTER TYPE migration every time
    # (same reasoning as Notification.type).
    eventType = Column('event_type', String, nullable=False)
    amount = Column('amount', Integer, nullable=False)
    occurredAt = Column("occurred_at", DateTime, default=datetime.now)
    source = Column('source', Enum("Manual", "Stripe", name='source_enum'), nullable=False)
    failureReason = Column('failure_reason', String, nullable=True)
    # Not "metadata" — that attribute name is reserved by SQLAlchemy's
    # Declarative API (every model already has a .metadata pointing at its
    # schema registry). Same fix as ItemRelationship.relationshipMetadata.
    billingMetadata = Column('metadata', JSONB)