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


class BillingInfo(Base):
    __tablename__ = "billing_info"

    # One row per subproject; subprojectId is both PK and FK.
    subprojectId = Column(
        "subproject_id",
        UUID(as_uuid=True),
        ForeignKey("subprojects.subproject_id", ondelete="RESTRICT"),
        primary_key=True,
    )
    totalInvoiced = Column("total_invoiced", Numeric(12, 2))
    totalPaid = Column("total_paid", Numeric(12, 2))
    totalRefunded = Column("total_refunded", Numeric(12, 2))
    balanceDue = Column("balance_due", Numeric(12, 2))
    status = Column(
        "status",
        Enum(
            "payment_pending",
            "partial_payment_received",
            "paid_in_full",
            "overdue",
            name="billing_status_enum",
        ),
        nullable=False,
    )
    lastEventAt = Column("last_event_at", DateTime(timezone=True), nullable=False)
