from sqlalchemy import Column, String, DateTime, Enum, ForeignKey, Table, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from database import Base


class Project(Base):
    __tablename__ = "projects"

    projectName = Column("project_name", String, nullable=False)
    projectId = Column(
        "project_id",
        UUID(as_uuid=True),
        nullable=False,
        primary_key=True,
        default=uuid.uuid4,
    )
    projectStatus = Column(
        "project_status",
        Enum(
            "Proposal",
            "Accepted",
            "Rejected",
            "Suggested Changes",
            "Planning",
            "Complete",
            name="project_status_enum",
        ),
    )
    projectStartDate = Column("project_start_date", DateTime, default=datetime.now)
    projectEndDate = Column("project_end_date", DateTime, default=datetime.now)
    vendorOnProject = Column(
        "vendor_on_project",
        UUID(as_uuid=True),
        ForeignKey("user_data.user_id"),
        index=True,
    )
    # The tenant this project belongs to
    organizationId = Column(
        "organization_id",
        UUID(as_uuid=True),
        ForeignKey("organizations.org_id"),
        nullable=False,
        index=True,
    )
    # The invoice the client actually went ahead with; null until set explicitly.
    # use_alter=True: invoices already FKs to projects, so this avoids a circular FK.
    finalInvoiceId = Column(
        "final_invoice_id",
        UUID(as_uuid=True),
        ForeignKey(
            "invoices.invoice_id", use_alter=True, name="fk_projects_final_invoice_id"
        ),
        nullable=True,
        index=True,
    )

    vendor = relationship("User", foreign_keys=[vendorOnProject])
    # A project's clients. user_projects is the only record of who they are
    # and the only thing client access checks read.
    users = relationship("User", secondary="user_projects", back_populates="projects")
    finalInvoice = relationship("Invoice", foreign_keys=[finalInvoiceId])
    organization = relationship("Organization", foreign_keys=[organizationId])


user_projects = Table(
    "user_projects",
    Base.metadata,
    # Links go with either side, so deleting a project or user never fails on them
    Column(
        "user_id",
        UUID(as_uuid=True),
        ForeignKey("user_data.user_id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "project_id",
        UUID(as_uuid=True),
        ForeignKey("projects.project_id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Index("user_projects_project_id", "project_id"),
)
