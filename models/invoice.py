from sqlalchemy import Column, String, Float, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
import uuid
from database import Base


class Invoice(Base):
    __tablename__ = 'invoices'

    invoiceId = Column("invoice_id", UUID(as_uuid=True), nullable=False, primary_key=True, default=uuid.uuid4)
    invoiceStatus = Column("invoice_status", Enum('Generated', 'Assigned', 'Pending', 'Paid', 'Declined', name='invoice_status_enum'), nullable=False)
    invoiceAmount = Column("invoice_amount", Float, nullable=False)
    invoiceAssignedTo = Column("invoice_assigned_to", UUID(as_uuid=True), ForeignKey('user_data.user_id'), nullable=False)
