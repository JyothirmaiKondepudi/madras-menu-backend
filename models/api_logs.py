from sqlalchemy import (
    Column,
    String,
    DateTime,
    Integer,
    func,
    Index,
    ForeignKey,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET
from datetime import datetime
import uuid
from database import Base


class ApiLogs(Base):

    __tablename__ = "api_logs"
    __table_args__ = (
        Index("api_logs_occurred_at", "occurred_at"),
        Index("api_logs_user_occurred_at", "user_id", "occurred_at"),
        Index("api_logs_org_occurred_at", "org_id", "occurred_at"),
    )

    id = Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    occurredAt = Column(
        "occurred_at",
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    requestId = Column("request_id", UUID(as_uuid=True), nullable=False)
    method = Column("method", String, nullable=False)
    path = Column("path", String, nullable=False)
    route = Column("route", String)
    queryParams = Column("query_params", JSONB(none_as_null=True))
    statusCode = Column("status_code", Integer, nullable=False)
    duration_ms = Column("duration_ms", Integer, nullable=False)
    userId = Column(
        "user_id",
        UUID(as_uuid=True),
        ForeignKey("user_data.user_id", ondelete="SET NULL"),
    )
    orgId = Column(
        "org_id",
        UUID(as_uuid=True),
        ForeignKey("organizations.org_id", ondelete="SET NULL"),
    )
    ipAddress = Column(
        "ip_address",
        INET,
    )
    userAgent = Column("user_agent", String)
    error = Column("error", String)
