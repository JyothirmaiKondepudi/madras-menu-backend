from pydantic import BaseModel
from uuid import UUID
from typing import Literal

class InvoiceOut(BaseModel):
    invoiceId: UUID
    invoiceStatus: Literal['Generated', 'Assigned', 'Pending', 'Paid', 'Declined']
    invoiceAmount: float
    invoiceAssignedTo: UUID

    class Config:
        from_attributes = True


class InvoiceCreate(BaseModel):
    invoiceStatus: Literal['Generated', 'Assigned', 'Pending', 'Paid', 'Declined']
    invoiceAmount: float
    invoiceAssignedTo: UUID


class InvoiceUpdate(BaseModel):
    invoiceStatus: Literal['Generated', 'Assigned', 'Pending', 'Paid', 'Declined'] | None = None
    invoiceAmount: float | None = None
    invoiceAssignedTo: UUID | None = None
