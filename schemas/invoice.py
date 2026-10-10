from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field, field_validator
from uuid import UUID
from typing import Literal

from schemas.project import ProjectOut


class InvoiceOut(BaseModel):
    invoiceId: UUID
    invoiceStatus: Literal["Assigned", "Accepted", "Paid", "Declined"]
    invoiceAmount: Decimal
    totalAmount: Decimal | None = None
    depositPercentage: Decimal | None = None
    invoiceAssignedTo: UUID
    projectAssociatedTo: UUID
    subprojectId: UUID | None = None
    project: ProjectOut
    createdAt: datetime
    updatedAt: datetime
    dueDate: datetime | None = None
    invoiceDeletedAt: datetime | None = None
    model_config = ConfigDict(from_attributes=True)


class InvoiceCreate(BaseModel):
    # no invoiceStatus: new invoices are always Assigned (services/invoice_status.py)
    # invoiceAmount isn't sent: it's totalAmount * depositPercentage / 100
    totalAmount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    depositPercentage: Decimal = Field(gt=0, le=100, max_digits=5, decimal_places=2)
    invoiceAssignedTo: UUID
    projectAssociatedTo: UUID
    subprojectId: UUID | None = None
    dueDate: datetime | None = None


class InvoiceUpdate(BaseModel):
    # no invoiceStatus: it only changes through accept, reject and payments
    totalAmount: Decimal | None = Field(
        default=None, gt=0, max_digits=12, decimal_places=2
    )
    depositPercentage: Decimal | None = Field(
        default=None, gt=0, le=100, max_digits=5, decimal_places=2
    )
    invoiceAssignedTo: UUID | None = None
    subprojectId: UUID | None = None
    dueDate: datetime | None = None

    # Leaving it out keeps the current client; an explicit null would try to
    # remove the client, which the NOT NULL column rejects (it was a 500).
    # Validators don't run on the default, so only an explicit null gets here.
    @field_validator("invoiceAssignedTo")
    @classmethod
    def _client_cant_be_removed(cls, value):
        if value is None:
            raise ValueError("an invoice must stay assigned to a client")
        return value
