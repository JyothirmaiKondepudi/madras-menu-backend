from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime

class AccountActivityOut(BaseModel):
    id: UUID
    projectId: UUID | None = None
    subprojectId: UUID | None = None
    activityType: str
    description: str
    actorId: UUID | None = None
    occurredAt: datetime
    activityMetadata: dict | None = None

    model_config = ConfigDict(from_attributes=True)
