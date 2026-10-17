from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime


class APILogs(BaseModel):
    id: UUID
    occurredAt: datetime
    requestId: UUID
    method: str
    path: str
    route: str | None = None
    queryParams: dict[str, str]
    statusCode: int
    duration_ms: int
    userId: UUID | None = None
    orgId: UUID | None = None
    ipAddress: str | None = None
    userAgent: str | None = None
    error: str | None = None
