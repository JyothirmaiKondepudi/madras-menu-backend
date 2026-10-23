from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
import uuid
from database import Base
from services.invoice_status import INVOICE_STATUSES


class Invoice(Base):
    __tablename__ = "invoices"
    # Each parent is checked by its own foreign key below; these two check the
    # parents against each other. Named explicitly: the naming convention would
    # give them the same names as the single-column foreign keys.
    __table_args__ = (
        # the billed client must be linked to the invoice's project
        ForeignKeyConstraint(
            ["invoice_assigned_to", "project_associated_to"],
            ["user_projects.user_id", "user_projects.project_id"],
            name="invoices_assignee_project_member_fkey",
            ondelete="RESTRICT",
        ),
        # the subproject must belong to the invoice's project; Postgres skips
        # the check when subproject_id is null (project-level invoices)
        ForeignKeyConstraint(
            ["subproject_id", "project_associated_to"],
            ["subprojects.subproject_id", "subprojects.project_associated_to"],
            name="invoices_subproject_in_project_fkey",
            ondelete="RESTRICT",
        ),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="invoices_currency_check"),
        CheckConstraint(
            "adjustment_percentage BETWEEN -100 AND 100",
            name="invoices_adjustment_percentage_check",
        ),
    )

    invoiceId = Column(
        "invoice_id",
        UUID(as_uuid=True),
        nullable=False,
        primary_key=True,
        default=uuid.uuid4,
    )
    invoiceStatus = Column(
        "invoice_status",
        # see services/invoice_status.py for the lifecycle
        Enum(*INVOICE_STATUSES, name="invoice_status_enum"),
        nullable=False,
    )
    invoiceAmount = Column("invoice_amount", Numeric(12, 2), nullable=False)
    invoiceAssignedTo = Column(
        "invoice_assigned_to",
        UUID(as_uuid=True),
        ForeignKey("user_data.user_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    invoiceDeletedAt = Column(
        "invoice_deleted_at",
        DateTime(timezone=True),
        nullable=True,
    )
    # A project can have many invoices (deposit, balance, add-ons).
    projectAssociatedTo = Column(
        "project_associated_to",
        UUID(as_uuid=True),
        ForeignKey("projects.project_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    # Null for project-level invoices (e.g. a deposit).
    subprojectId = Column(
        "subproject_id",
        UUID(as_uuid=True),
        ForeignKey("subprojects.subproject_id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    createdAt = Column(
        "created_at", DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updatedAt = Column(
        "updated_at",
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    # invoiceAmount is computed from these two (see services/invoices.py).
    # Nullable: invoices created before deposits existed have neither.
    totalAmount = Column("total_amount", Numeric(12, 2))
    depositPercentage = Column("deposit_percentage", Numeric(5, 2))  # 25 = 25%
    dueDate = Column("due_date", DateTime(timezone=True), nullable=True, index=True)

    # --- the invoice document (BE-04) ---
    # per organization and year, e.g. INV-2026-0001 (services/invoice_document.py);
    # never reused, even if the invoice is deleted. Not unique across the
    # table: every organization has its own INV-2026-0001. The counter hands
    # each number out once per organization.
    invoiceNumber = Column("invoice_number", String, index=True)
    # ISO 4217 code
    currency = Column(String(3), nullable=False, server_default=text("'USD'"))
    # sum of the line items; null for invoices entered as a single total
    subtotalAmount = Column("subtotal_amount", Numeric(12, 2))
    # applied to the subtotal: -10 is a 10% discount, 5 a 5% surcharge
    adjustmentPercentage = Column("adjustment_percentage", Numeric(5, 2))
    legalTerms = Column("legal_terms", Text)
    deliverables = Column(Text)
    # the business and client as they were when the invoice was issued: kept
    # current while it's editable (Assigned), frozen once the client accepts
    businessSnapshot = Column("business_snapshot", JSONB)
    clientSnapshot = Column("client_snapshot", JSONB)
    # Explicit foreign_keys: Project.finalInvoiceId adds a second FK path.
    project = relationship("Project", foreign_keys=[projectAssociatedTo])
    # explicit foreign_keys: invoices_subproject_in_project_fkey is a second path to subprojects
    subproject = relationship("Subproject", foreign_keys=[subprojectId])
    lineItems = relationship(
        "InvoiceLineItem",
        order_by="InvoiceLineItem.position",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
