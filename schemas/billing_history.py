from decimal import Decimal
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints
from typing import Annotated, Literal
from uuid import UUID
from datetime import datetime


class BillingHistoryOut(BaseModel):
    id: UUID
    invoiceId: UUID
    eventType: Literal[
        "Payment_Succeeded",
        "Payment_Declined",
        "Payment_Pending",
        "Refund_Initiated",
        "Refund_Issued",
    ]
    amount: Decimal | None = None
    occurredAt: datetime
    source: Literal["Manual", "Stripe"]
    failureReason: str | None = None
    billingMetadata: dict | None = None
    voidedAt: datetime | None = None
    voidedReason: str | None = None

    model_config = ConfigDict(from_attributes=True)


class PaymentCreate(BaseModel):
    """Body for POST /billing-history/payments — recording that a payment
    was made. eventType and source aren't caller-settable: this route only
    ever records a successful, manually-entered payment (source="Manual"),
    never a Stripe-sourced row — those arrive via a webhook handler later,
    not this endpoint."""

    invoiceId: UUID
    amount: Decimal = Field(
        gt=0, max_digits=12, decimal_places=2, description="Payment amount in dollars"
    )
    # must include a timezone offset
    occurredAt: AwareDatetime | None = None
    billingMetadata: dict | None = None


class VoidPaymentRequest(BaseModel):
    """Why the payment is being voided, e.g. "Typo, actual amount was $150"."""

    reason: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)
    ]
