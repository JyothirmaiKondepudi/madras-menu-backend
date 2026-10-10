from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field
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
