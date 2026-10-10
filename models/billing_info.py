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
from datetime import datetime, timezone

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
            "no_active_invoices",
            name="billing_status_enum",
        ),
        nullable=False,
    )
    # earliest due date among invoices that still owe money; set by the recompute
    nextDueDate = Column("next_due_date", DateTime(timezone=True), nullable=True)
    lastEventAt = Column("last_event_at", DateTime(timezone=True), nullable=False)

    @property
    def currentStatus(self):
        """overdue depends on today's date, so it's decided when read rather
        than stored: nothing happens in the app when a due date passes."""
        if (
            self.balanceDue > 0
            and self.nextDueDate is not None
            and self.nextDueDate < datetime.now(timezone.utc)
        ):
            return "overdue"
        return self.status
