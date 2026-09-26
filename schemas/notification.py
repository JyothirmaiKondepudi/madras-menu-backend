from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime


class NotificationOut(BaseModel):
    id: UUID
    type: str
    message: str
    relatedInvoiceId: UUID | None = None
    relatedUserId: UUID | None = None
    seenAt: datetime | None = None
    readAt: datetime | None = None
    createdAt: datetime

    model_config = ConfigDict(from_attributes=True)
