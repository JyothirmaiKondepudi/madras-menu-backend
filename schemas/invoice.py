from pydantic import BaseModel, ConfigDict, Field
from uuid import UUID
from typing import Literal

from schemas.project import ProjectOut


class InvoiceOut(BaseModel):
    invoiceId: UUID
    invoiceStatus: Literal[
        "Generated", "Assigned", "Pending", "Accepted", "Paid", "Declined"
    ]
    invoiceAmount: float
    totalAmount: float | None = None
    depositPercentage: float | None = None
    invoiceAssignedTo: UUID
    projectAssociatedTo: UUID
    subprojectId: UUID | None = None
    project: ProjectOut

    model_config = ConfigDict(from_attributes=True)


class InvoiceCreate(BaseModel):
    invoiceStatus: Literal[
        "Generated", "Assigned", "Pending", "Accepted", "Paid", "Declined"
    ]
    # invoiceAmount isn't sent: it's totalAmount * depositPercentage / 100
    totalAmount: float = Field(gt=0)
    depositPercentage: float = Field(gt=0, le=100)
    invoiceAssignedTo: UUID
    projectAssociatedTo: UUID
    subprojectId: UUID | None = None


class InvoiceUpdate(BaseModel):
    invoiceStatus: (
        Literal["Generated", "Assigned", "Pending", "Accepted", "Paid", "Declined"]
        | None
    ) = None
    totalAmount: float | None = Field(default=None, gt=0)
    depositPercentage: float | None = Field(default=None, gt=0, le=100)
    invoiceAssignedTo: UUID | None = None
    projectAssociatedTo: UUID | None = None
    subprojectId: UUID | None = None
