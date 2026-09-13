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
    project_invoice = Column('projectInvoice', UUID(as_uuid=True), ForeignKey('invoices.invoice_id'))

    client = relationship('User', foreign_keys=[clientId])
    admin = relationship('User', foreign_keys=[adminOnProject])


user_projects = Table(
    'user_projects',
    Base.metadata,
    Column('user_id', UUID(as_uuid=True), ForeignKey('user_data.user_id'), primary_key=True),
    Column('project_id', UUID(as_uuid=True), ForeignKey('projects.project_id'), primary_key=True)
)
