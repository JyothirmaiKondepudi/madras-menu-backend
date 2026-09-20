from pydantic import BaseModel, ConfigDict
from uuid import UUID
from typing import Literal

from schemas.project import ProjectOut

class InvoiceOut(BaseModel):
    invoiceId: UUID
    invoiceStatus: Literal['Generated', 'Assigned', 'Pending', 'Paid', 'Declined']
    invoiceAmount: float
    invoiceAssignedTo: UUID
    projectAssociatedTo: UUID
    project: ProjectOut

    model_config = ConfigDict(from_attributes=True)


class InvoiceCreate(BaseModel):
    invoiceStatus: Literal['Generated', 'Assigned', 'Pending', 'Paid', 'Declined']
    invoiceAmount: float
    invoiceAssignedTo: UUID
    projectAssociatedTo: UUID


class InvoiceUpdate(BaseModel):
    invoiceStatus: Literal['Generated', 'Assigned', 'Pending', 'Paid', 'Declined'] | None = None
    invoiceAmount: float | None = None
    invoiceAssignedTo: UUID | None = None
    projectAssociatedTo: UUID | None = None
