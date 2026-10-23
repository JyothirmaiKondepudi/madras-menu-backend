from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, field_serializer


class TimelineEntryOut(BaseModel):
    """One entry on a project's timeline: an activity (project created,
    invoice accepted, followed up, ...) or a payment event."""

    id: UUID
    kind: Literal["activity", "payment"]
    # an activity type (invoice_accepted, followed_up, ...) or a payment
    # event type (Payment_Succeeded, Refund_Issued, ...)
    type: str
    description: str
    occurredAt: datetime
    actorId: UUID | None = None
    subprojectId: UUID | None = None
    # payments only
    amount: Decimal | None = None
    voidedAt: datetime | None = None

    @field_serializer("amount", when_used="json")
    def _decimal_as_number(self, value: Decimal | None) -> float | None:
        return None if value is None else float(value)
