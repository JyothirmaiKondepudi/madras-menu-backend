from decimal import Decimal
from pydantic import BaseModel, ConfigDict
from typing import Literal
from uuid import UUID
from datetime import datetime

class BillingInfoOut(BaseModel):
    subprojectId: UUID
    totalInvoiced: Decimal
    totalPaid: Decimal
    totalRefunded: Decimal
    balanceDue: Decimal
    status: Literal['payment_pending', 'partial_payment_received', 'paid_in_full', 'overdue']
    lastEventAt: datetime

    model_config = ConfigDict(from_attributes=True)
