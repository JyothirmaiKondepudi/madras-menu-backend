from pydantic import BaseModel
from uuid import UUID

class InvoiceOut(BaseModel):
    invoiceId: UUID
    invoiceStatus: str
    invoiceAmount: float
    class Config:
        from_attributes = True
