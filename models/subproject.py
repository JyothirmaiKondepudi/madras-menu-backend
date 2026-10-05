from sqlalchemy import (
    Column,
    String,
    DateTime,
    Integer,
    CheckConstraint,
    ForeignKey,
    func,
    ARRAY,
    Numeric,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from database import Base
from models.choices import EventType, Religion, ServiceStyle, Venue, check_in
from services.timezones import to_local


class Subproject(Base):
    __tablename__ = "subprojects"
    __table_args__ = (
        # value lists live in models/choices.py; see there for how to change one
        CheckConstraint(
            check_in("religion", Religion), name="subprojects_religion_check"
        ),
        CheckConstraint(
            check_in("subproject_type", ServiceStyle),
            name="subprojects_subproject_type_check",
        ),
        CheckConstraint(check_in("venue", Venue), name="subprojects_venue_check"),
        CheckConstraint(
            check_in("subproject_event", EventType),
            name="subprojects_subproject_event_check",
        ),
    )

    subprojectId = Column(
        "subproject_id",
        UUID(as_uuid=True),
        nullable=False,
        primary_key=True,
        default=uuid.uuid4,
    )
    subprojectName = Column("subproject_name", String, nullable=False)
    projectAssociatedTo = Column(
        "project_associated_to",
        UUID(as_uuid=True),
        ForeignKey("projects.project_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    cuisine = Column("cuisine", ARRAY(String))
    religion = Column("religion", String)
    subprojectDate = Column("subproject_date", DateTime(timezone=True), nullable=False)
    guestCount = Column("guest_count", Integer, nullable=False)
    subprojectType = Column("subproject_type", String, nullable=False)
    subprojectVenue = Column("venue", String, nullable=False)
    subprojectEvent = Column("subproject_event", String, nullable=False)
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
    minPricePerPerson = Column("min_price_per_person", Numeric(12, 2))
    maxPricePerPerson = Column("max_price_per_person", Numeric(12, 2))

    project = relationship("Project")

    @property
    def effectiveTimezone(self) -> str:
        return self.project.effectiveTimezone

    @property
    def localSubprojectDate(self):
        return to_local(self.subprojectDate, self.effectiveTimezone)
