from sqlalchemy import Column, String, Float, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from database import Base


class Invoice(Base):
    __tablename__ = 'invoices'

    invoiceId = Column("invoice_id", UUID(as_uuid=True), nullable=False, primary_key=True, default=uuid.uuid4)
    invoiceStatus = Column("invoice_status", Enum('Generated', 'Assigned', 'Pending', 'Accepted', 'Paid', 'Declined', name='invoice_status_enum'), nullable=False)
    invoiceAmount = Column("invoice_amount", Float, nullable=False)
    invoiceAssignedTo = Column("invoice_assigned_to", UUID(as_uuid=True), ForeignKey('user_data.user_id'), nullable=False)
    # A project can have more than one invoice over its lifecycle (deposit,
    # balance, add-ons) — same shape as Subproject.projectAssociatedTo, not a
    # one-to-one. Replaces the old, never-populated Project.project_invoice.
    projectAssociatedTo = Column("project_associated_to", UUID(as_uuid=True), ForeignKey('projects.project_id'), nullable=False)
    # Nullable: which specific subproject (if any) this invoice was
    # generated for — a project can have several subprojects, so knowing
    # the project alone isn't enough to say which one a given invoice (and
    # its billing history) belongs to. Null covers project-level invoices
    # (e.g. a deposit) not tied to one particular subproject.
    subprojectId = Column("subproject_id", UUID(as_uuid=True), ForeignKey('subprojects.subproject_id'), nullable=True)

    # foreign_keys explicit now that Project.finalInvoiceId creates a second,
    # opposite-direction FK path between these two tables — without this,
    # SQLAlchemy can't tell which one defines "an invoice's own project."
    project = relationship('Project', foreign_keys=[projectAssociatedTo])
    subproject = relationship('Subproject')
