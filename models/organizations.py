from sqlalchemy import Column, String, DateTime, Index, ForeignKey, text, func, Boolean
from sqlalchemy.dialects.postgresql import JSONB, UUID
import uuid
from database import Base


class Organization(Base):
    __tablename__ = "organizations"

    orgId = Column("org_id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    orgName = Column("org_name", String, nullable=False)
    orgCreatedAt = Column("org_created_at", DateTime(timezone=True), server_default=func.now(), nullable=False)
    orgEmail = Column("org_email", String, nullable=False)
    orgDisabled = Column("org_disabled", Boolean, nullable=False)
    # IANA name; the default timezone for this caterer's events (see services/timezones.py)
    orgTimezone = Column("org_timezone", String, server_default="America/New_York", nullable=False)
    orgUpdatedAt = Column(
        "org_updated_at",
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
