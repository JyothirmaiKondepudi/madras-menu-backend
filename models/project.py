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
    vendorOnProject = Column("vendor_on_project", UUID(as_uuid=True), ForeignKey('user_data.user_id'))
    clientId = Column("client_id", UUID(as_uuid=True), ForeignKey('user_data.user_id'), nullable=False)
    # The tenant this project belongs to — nullable only because existing
    # rows predate Organization; set automatically from the creating
    # vendor's own org, never client-supplied. Invoice/Subproject scope by
    # joining through here rather than each carrying their own copy, so
    # there's exactly one place a project's org can drift from.
    organizationId = Column("organization_id", UUID(as_uuid=True), ForeignKey('organizations.org_id'), nullable=True)
    # The invoice the client actually went ahead with; null until set explicitly.
    # use_alter=True: invoices already FKs to projects, so this avoids a circular FK.
    finalInvoiceId = Column(
        "final_invoice_id",
        UUID(as_uuid=True),
        ForeignKey('invoices.invoice_id', use_alter=True, name='fk_projects_final_invoice_id'),
        nullable=True,
    )

    client = relationship('User', foreign_keys=[clientId])
    vendor = relationship('User', foreign_keys=[vendorOnProject])
    users = relationship('User', secondary='user_projects', back_populates='projects')
    finalInvoice = relationship('Invoice', foreign_keys=[finalInvoiceId])
    organization = relationship('Organization', foreign_keys=[organizationId])


user_projects = Table(
    'user_projects',
    Base.metadata,
    Column('user_id', UUID(as_uuid=True), ForeignKey('user_data.user_id'), primary_key=True),
    Column('project_id', UUID(as_uuid=True), ForeignKey('projects.project_id'), primary_key=True)
)
