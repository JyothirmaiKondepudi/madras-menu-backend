from sqlalchemy import Column, String, Enum, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from database import Base


class Invoice(Base):
    __tablename__ = "invoices"

    invoiceId = Column(
        "invoice_id",
        UUID(as_uuid=True),
        nullable=False,
        primary_key=True,
        default=uuid.uuid4,
    )
    invoiceStatus = Column(
        "invoice_status",
        Enum(
            "Generated",
            "Assigned",
            "Pending",
            "Accepted",
            "Paid",
            "Declined",
            name="invoice_status_enum",
        ),
        nullable=False,
    )
    invoiceAmount = Column("invoice_amount", Numeric(12, 2), nullable=False)
    invoiceAssignedTo = Column(
        "invoice_assigned_to",
        UUID(as_uuid=True),
        ForeignKey("user_data.user_id"),
        nullable=False,
        index=True,
    )
    # A project can have many invoices (deposit, balance, add-ons).
    projectAssociatedTo = Column(
        "project_associated_to",
        UUID(as_uuid=True),
        ForeignKey("projects.project_id"),
        nullable=False,
        index=True,
    )
    # Null for project-level invoices (e.g. a deposit).
    subprojectId = Column(
        "subproject_id",
        UUID(as_uuid=True),
        ForeignKey("subprojects.subproject_id"),
        nullable=True,
        index=True,
    )
    # invoiceAmount is computed from these two (see services/invoices.py).
    # Nullable: invoices created before deposits existed have neither.
    totalAmount = Column("total_amount", Numeric(12, 2))
    depositPercentage = Column("deposit_percentage", Numeric(5, 2))  # 25 = 25%
    # Explicit foreign_keys: Project.finalInvoiceId adds a second FK path.
    project = relationship("Project", foreign_keys=[projectAssociatedTo])
    subproject = relationship("Subproject")
