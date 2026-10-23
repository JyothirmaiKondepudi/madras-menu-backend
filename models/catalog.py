"""An organization's own price lists (BE-07): the rate card of services it
sells, and the equipment it charges for. Pickers in the project wizard and,
later, invoice line items (BE-04) read these. Both belong to one
organization and go with it if it's deleted."""

import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID

from database import Base
from models.choices import PricingUnit, check_in


class RateCardItem(Base):
    __tablename__ = "rate_card"
    __table_args__ = (
        CheckConstraint(check_in("pricing_unit", PricingUnit), name="rate_card_pricing_unit_check"),
        CheckConstraint("price >= 0", name="rate_card_price_check"),
        CheckConstraint("hours IS NULL OR hours > 0", name="rate_card_hours_check"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    orgId = Column(
        "org_id",
        UUID(as_uuid=True),
        ForeignKey("organizations.org_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String, nullable=False)
    # dollars, like invoices
    price = Column(Numeric(12, 2), nullable=False)
    pricingUnit = Column("pricing_unit", String, nullable=False)
    # how long the service runs, when that's part of the offer (e.g. 4 hours of bar service)
    hours = Column(Numeric(5, 2))
    # free text for now (e.g. "Staffing", "Bar"), until the frontend's list is known
    category = Column(String)
    # inactive items stay for history but are hidden from pickers
    active = Column(Boolean, nullable=False, server_default=text("true"))
    createdAt = Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False)
    updatedAt = Column(
        "updated_at", DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Equipment(Base):
    __tablename__ = "equipment"
    __table_args__ = (CheckConstraint("amount >= 0", name="equipment_amount_check"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    orgId = Column(
        "org_id",
        UUID(as_uuid=True),
        ForeignKey("organizations.org_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String, nullable=False)
    # the default price charged for it, in dollars (an invoice line sets the quantity)
    amount = Column(Numeric(12, 2), nullable=False)
    active = Column(Boolean, nullable=False, server_default=text("true"))
    createdAt = Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False)
    updatedAt = Column(
        "updated_at", DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
