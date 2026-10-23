"""Parts of the invoice document (BE-04): its line items, and the counters
that hand out invoice numbers."""

import uuid

from sqlalchemy import CheckConstraint, Column, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID

from database import Base


class InvoiceLineItem(Base):
    """One line on an invoice. A line picked from the rate card or equipment
    list copies its name and price, so editing the catalog later doesn't
    change invoices already written; sourceId records where it came from."""

    __tablename__ = "invoice_line_items"
    __table_args__ = (
        CheckConstraint("kind IN ('service', 'equipment', 'custom')", name="invoice_line_items_kind_check"),
        CheckConstraint("quantity > 0", name="invoice_line_items_quantity_check"),
        CheckConstraint("unit_price >= 0", name="invoice_line_items_unit_price_check"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoiceId = Column(
        "invoice_id",
        UUID(as_uuid=True),
        ForeignKey("invoices.invoice_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # order on the invoice, from 0
    position = Column(Integer, nullable=False)
    kind = Column(String, nullable=False)
    # the rate card item or equipment it was copied from; no foreign key, so
    # deleting a catalog item leaves invoices alone
    sourceId = Column("source_id", UUID(as_uuid=True))
    name = Column(String, nullable=False)
    quantity = Column(Numeric(10, 2), nullable=False)
    unitPrice = Column("unit_price", Numeric(12, 2), nullable=False)
    # guest / hour / event / tray, for rate card lines
    pricingUnit = Column("pricing_unit", String)
    # quantity * unitPrice, rounded to the cent
    lineTotal = Column("line_total", Numeric(12, 2), nullable=False)


class InvoiceNumberCounter(Base):
    """The last invoice number used, per organization and year."""

    __tablename__ = "invoice_number_counters"

    orgId = Column(
        "org_id",
        UUID(as_uuid=True),
        ForeignKey("organizations.org_id", ondelete="CASCADE"),
        primary_key=True,
    )
    year = Column(Integer, primary_key=True)
    lastNumber = Column("last_number", Integer, nullable=False)
