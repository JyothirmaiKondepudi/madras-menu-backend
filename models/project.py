from sqlalchemy import Column, String, DateTime, Enum, ForeignKey, Table, Index, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from database import Base
from services.timezones import effective_timezone, to_local


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
    projectStartDate = Column("project_start_date", DateTime(timezone=True), nullable=True)
    projectEndDate = Column("project_end_date", DateTime(timezone=True), nullable=True)
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
    # IANA name of the venue's timezone when it differs from the org's; null = use the org's
    projectTimezone = Column("project_timezone", String, nullable=True)
    createdAt = Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False)
    updatedAt = Column(
        "updated_at",
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    vendor = relationship("User", foreign_keys=[vendorOnProject])
    # A project's clients. user_projects is the only record of who they are
    # and the only thing client access checks read.
    users = relationship("User", secondary="user_projects", back_populates="projects")
    finalInvoice = relationship("Invoice", foreign_keys=[finalInvoiceId])
    organization = relationship("Organization", foreign_keys=[organizationId])

    @property
    def effectiveTimezone(self) -> str:
        return effective_timezone(self)

    @property
    def localStartDate(self):
        return to_local(self.projectStartDate, self.effectiveTimezone)

    @property
    def localEndDate(self):
        return to_local(self.projectEndDate, self.effectiveTimezone)


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
