from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field
from uuid import UUID
from typing import Literal

from schemas.project import ProjectOut


class InvoiceOut(BaseModel):
    invoiceId: UUID
    invoiceStatus: Literal[
        "Generated", "Assigned", "Pending", "Accepted", "Paid", "Declined"
    ]
    invoiceAmount: Decimal
    totalAmount: Decimal | None = None
    depositPercentage: Decimal | None = None
    invoiceAssignedTo: UUID
    projectAssociatedTo: UUID
    subprojectId: UUID | None = None
    project: ProjectOut
    createdAt: datetime
    updatedAt: datetime

    model_config = ConfigDict(from_attributes=True)


class InvoiceCreate(BaseModel):
    invoiceStatus: Literal[
        "Generated", "Assigned", "Pending", "Accepted", "Paid", "Declined"
    ]
    # invoiceAmount isn't sent: it's totalAmount * depositPercentage / 100
    totalAmount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    depositPercentage: Decimal = Field(gt=0, le=100, max_digits=5, decimal_places=2)
    invoiceAssignedTo: UUID
    projectAssociatedTo: UUID
    subprojectId: UUID | None = None


class InvoiceUpdate(BaseModel):
    invoiceStatus: (
        Literal["Generated", "Assigned", "Pending", "Accepted", "Paid", "Declined"]
        | None
    ) = None
    totalAmount: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    depositPercentage: Decimal | None = Field(default=None, gt=0, le=100, max_digits=5, decimal_places=2)
    invoiceAssignedTo: UUID | None = None
    subprojectId: UUID | None = None
