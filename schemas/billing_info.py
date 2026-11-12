from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field, field_serializer
from typing import Literal
from uuid import UUID
from datetime import datetime


class BillingInfoOut(BaseModel):
    subprojectId: UUID
    totalInvoiced: Decimal
    totalPaid: Decimal
    totalRefunded: Decimal
    balanceDue: Decimal
    # read from currentStatus, which adds overdue on top of the stored status
    status: Literal[
        "payment_pending",
        "partial_payment_received",
        "paid_in_full",
        "overdue",
        "no_active_invoices",
    ] = Field(validation_alias="currentStatus")
    nextDueDate: datetime | None = None
    lastEventAt: datetime

    model_config = ConfigDict(from_attributes=True)

    # Decimal inside the app, a plain JSON number on the way out: the
    # frontend only displays these, it never does arithmetic on them
    @field_serializer("totalInvoiced", "totalPaid", "totalRefunded", "balanceDue", when_used="json")
    def _decimal_as_number(self, value: Decimal | None) -> float | None:
        return None if value is None else float(value)
