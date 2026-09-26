from pydantic import BaseModel, ConfigDict, Field
from typing import Literal
from uuid import UUID
from datetime import datetime

class BillingHistoryOut(BaseModel):
    id: UUID
    invoiceId: UUID
    eventType: Literal['Payment_Succeeded', "Payment_Declined", "Payment_Pending", "Refund_Initiated", "Refund_Issued"]
    amount: int | None = None
    occurredAt: datetime
    source: Literal["Manual", "Stripe"]
    failureReason: str | None = None
    billingMetadata: dict | None = None

    model_config = ConfigDict(from_attributes=True)


class PaymentCreate(BaseModel):
    """Body for POST /billing-history/payments — recording that a payment
    was made. eventType and source aren't caller-settable: this route only
    ever records a successful, manually-entered payment (source="Manual"),
    never a Stripe-sourced row — those arrive via a webhook handler later,
    not this endpoint."""
    invoiceId: UUID
    amount: int = Field(gt=0, description="Payment amount in cents")
    occurredAt: datetime | None = None
    billingMetadata: dict | None = None
