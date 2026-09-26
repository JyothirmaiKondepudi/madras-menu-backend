from sqlalchemy import Column, String, DateTime, Float, Integer, Enum, ForeignKey, ARRAY
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
from database import Base


class BillingInfo(Base):
    __tablename__ = 'billing_info'

    # One row per subproject — subprojectId IS the primary key, not a
    # separate generated id, and it's a real FK so this can't ever point at
    # a subproject that doesn't exist.
    subprojectId = Column('subproject_id', UUID(as_uuid=True), ForeignKey('subprojects.subproject_id'), primary_key=True)
    totalInvoiced = Column("total_invoiced", Float)
    totalPaid = Column('total_paid', Float)
    totalRefunded = Column('total_refunded', Float)
    balanceDue = Column("balance_due", Float)
    status = Column('status', Enum('payment_pending', 'partial_payment_received', 'paid_in_full', 'overdue', name='billing_status_enum'), nullable=False)
    lastEventAt = Column('last_event_at', DateTime, nullable=False)