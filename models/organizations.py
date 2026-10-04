from sqlalchemy import Column, String, DateTime, Index, ForeignKey, text, func, Boolean
from sqlalchemy.dialects.postgresql import JSONB, UUID
from datetime import datetime
import uuid
from database import Base


class Organization(Base):
    __tablename__ = "organizations"

    orgId = Column("org_id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    orgName = Column("org_name", String, nullable=False)
    orgCreatedAt = Column("org_created_at", DateTime, default=datetime.now)
    orgEmail = Column("org_email", String, nullable=False)
    orgDisabled = Column("org_disabled", Boolean, nullable=False)
