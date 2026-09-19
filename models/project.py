from sqlalchemy import Column, String, DateTime, Enum, ForeignKey, Table
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from database import Base


class Project(Base):
    __tablename__ = 'projects'

    projectName = Column("project_name", String, nullable=False)
    projectId = Column("project_id", UUID(as_uuid=True), nullable=False, primary_key=True, default=uuid.uuid4)
    projectStatus = Column("project_status", Enum('Proposal', 'Accepted', 'Rejected', 'Suggested Changes', 'Planning', 'Complete', name='project_status_enum'))
    projectStartDate = Column("project_start_date", DateTime, default=datetime.now)
    projectEndDate = Column("project_end_date", DateTime, default=datetime.now)
    adminOnProject = Column("admin_on_project", UUID(as_uuid=True), ForeignKey('user_data.user_id'))
    clientId = Column("client_id", UUID(as_uuid=True), ForeignKey('user_data.user_id'), nullable=False)
    # A project can have several invoices over time (revisions, drafts) —
    # this points at the one the client actually went ahead with, so the
    # admin has a single answer to "which invoice is the real one for this
    # project." Null until explicitly set (see PATCH
    # /projects/{id}/final-invoice/{invoice_id}) — never inferred from
    # invoiceStatus or "most recent," since neither reliably means "the
    # client accepted this one."
    # use_alter=True + an explicit name: invoices.project_associated_to
    # already points at projects, so this column creates a genuine cycle
    # between the two tables. Without use_alter, Base.metadata.create_all()
    # (what the test suite uses to build a fresh schema) silently drops one
    # of the two FK constraints instead of erroring — caught for real when
    # test_projects.py started raising IntegrityError on insert. use_alter
    # defers this one constraint to a separate ALTER TABLE after both
    # tables exist, which resolves the cycle cleanly.
    finalInvoiceId = Column(
        "final_invoice_id",
        UUID(as_uuid=True),
        ForeignKey('invoices.invoice_id', use_alter=True, name='fk_projects_final_invoice_id'),
        nullable=True,
    )

    client = relationship('User', foreign_keys=[clientId])
    admin = relationship('User', foreign_keys=[adminOnProject])
    users = relationship('User', secondary='user_projects', back_populates='projects')
    finalInvoice = relationship('Invoice', foreign_keys=[finalInvoiceId])


user_projects = Table(
    'user_projects',
    Base.metadata,
    Column('user_id', UUID(as_uuid=True), ForeignKey('user_data.user_id'), primary_key=True),
    Column('project_id', UUID(as_uuid=True), ForeignKey('projects.project_id'), primary_key=True)
)
