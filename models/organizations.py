from sqlalchemy import ARRAY, Column, String, DateTime, Index, text, func, Boolean
from sqlalchemy.dialects.postgresql import JSONB, UUID
import uuid
from database import Base


class Organization(Base):
    __tablename__ = "organizations"

    orgId = Column("org_id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    orgName = Column("org_name", String, nullable=False)
    orgCreatedAt = Column(
        "org_created_at",
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    orgEmail = Column("org_email", String, nullable=False)
    orgDisabled = Column("org_disabled", Boolean, nullable=False)
    # IANA name; the default timezone for this caterer's events (see services/timezones.py)
    orgTimezone = Column(
        "org_timezone", String, server_default="America/New_York", nullable=False
    )
    # Business profile (BE-07), shown on the Profile page and invoice headers.
    # orgName is the business name.
    orgAddress = Column("org_address", String)
    orgPhone = Column("org_phone", String)
    # US employer identification number, stored as 12-3456789
    orgEin = Column("org_ein", String)
    # ISO 3166-1 alpha-2, e.g. "US"
    orgCountry = Column("org_country", String(2))
    # a link for now; uploading the image belongs with file storage (BE-20)
    orgLogoUrl = Column("org_logo_url", String)
    # network -> profile URL, e.g. {"instagram": "https://..."}
    orgSocials = Column("org_socials", JSONB, nullable=False, server_default=text("'{}'"))
    orgWebsites = Column(
        "org_websites", ARRAY(String), nullable=False, server_default=text("'{}'")
    )
    orgUpdatedAt = Column(
        "org_updated_at",
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
