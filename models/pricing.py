"""Organization-owned catering prices, independent of menu generation.

Base rates describe the base package. Each higher tier has explicit additions
to that package; tier position is display order, not implicit inheritance.
NULL conditions are wildcards. Matching/overlap resolution belongs to a future
pricing service, not to this storage model.
"""
import uuid

from sqlalchemy import (
    Boolean, CheckConstraint, Column, Date, DateTime, ForeignKey,
    ForeignKeyConstraint, Index, Integer, Numeric, String, UniqueConstraint,
    func, text,
)
from sqlalchemy.dialects.postgresql import UUID

from database import Base
from models.choices import Diet, EventType, ServiceStyle, check_in


class PricingRecord:
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    orgId = Column(
        "org_id", UUID(as_uuid=True),
        ForeignKey("organizations.org_id", ondelete="RESTRICT"), nullable=False,
    )
    active = Column(Boolean, nullable=False, server_default=text("true"), default=True)
    createdAt = Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now())
    updatedAt = Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class PricingTier(PricingRecord, Base):
    __tablename__ = "pricing_tiers"
    name = Column(String(100), nullable=False)
    position = Column(Integer, nullable=False)
    isBase = Column("is_base", Boolean, nullable=False, default=False, server_default=text("false"))
    description = Column(String)
    __table_args__ = (
        UniqueConstraint("org_id", "id", name="pricing_tiers_org_id_id_key"),
        UniqueConstraint("org_id", "position", name="pricing_tiers_org_position_key"),
        CheckConstraint("position >= 0", name="pricing_tiers_position_check"),
        CheckConstraint("length(trim(name)) > 0", name="pricing_tiers_name_check"),
        Index("pricing_tiers_org_name_key", "org_id", func.lower(name), unique=True),
        Index("pricing_tiers_one_active_base", "org_id", unique=True,
              postgresql_where=text("is_base AND active")),
    )


class PricingConditions:
    """Inclusive guest bounds; effective dates use [from, until)."""
    eventType = Column("event_type", String)
    serviceStyle = Column("service_style", String)
    diet = Column(String)
    minGuests = Column("min_guests", Integer, nullable=False, default=1, server_default="1")
    maxGuests = Column("max_guests", Integer)
    effectiveFrom = Column("effective_from", Date, nullable=False)
    effectiveUntil = Column("effective_until", Date)
    currency = Column(String(3), nullable=False)


def condition_constraints(name):
    return (
        CheckConstraint(check_in("event_type", EventType), name=f"{name}_event_check"),
        CheckConstraint(check_in("service_style", ServiceStyle), name=f"{name}_style_check"),
        CheckConstraint(check_in("diet", Diet), name=f"{name}_diet_check"),
        CheckConstraint("min_guests > 0 AND (max_guests IS NULL OR max_guests >= min_guests)", name=f"{name}_guests_check"),
        CheckConstraint("effective_until IS NULL OR effective_until > effective_from", name=f"{name}_dates_check"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name=f"{name}_currency_check"),
        Index(f"{name}_org_lookup", "org_id", "active", "currency", "effective_from"),
    )


class PricingBaseRate(PricingConditions, PricingRecord, Base):
    __tablename__ = "pricing_base_rates"
    name = Column(String(100), nullable=False)
    pricePerPerson = Column("price_per_person", Numeric(12, 2), nullable=False)
    minimumCharge = Column("minimum_charge", Numeric(12, 2), nullable=False, default=0, server_default="0")
    # Human-readable package scope until course-count/inclusion rules are agreed.
    inclusions = Column(String, nullable=False)
    __table_args__ = (
        *condition_constraints("pricing_base_rates"),
        CheckConstraint("price_per_person >= 0 AND minimum_charge >= 0", name="pricing_base_rates_amount_check"),
        CheckConstraint("length(trim(name)) > 0 AND length(trim(inclusions)) > 0", name="pricing_base_rates_description_check"),
    )


class PricingAdjustment(PricingConditions, PricingRecord, Base):
    __tablename__ = "pricing_adjustments"
    name = Column(String(100), nullable=False)
    tierId = Column("tier_id", UUID(as_uuid=True))
    # Optional shared dish identity; the amount is always organization-owned.
    menuItemId = Column("menu_item_id", UUID(as_uuid=True), ForeignKey("menu_items.id", ondelete="RESTRICT"))
    amount = Column(Numeric(12, 2), nullable=False)
    chargeUnit = Column("charge_unit", String, nullable=False)
    __table_args__ = (
        *condition_constraints("pricing_adjustments"),
        ForeignKeyConstraint(["org_id", "tier_id"], ["pricing_tiers.org_id", "pricing_tiers.id"], ondelete="RESTRICT", name="pricing_adjustments_tier_org_fkey"),
        CheckConstraint("amount >= 0", name="pricing_adjustments_amount_check"),
        CheckConstraint("charge_unit IN ('guest', 'event')", name="pricing_adjustments_unit_check"),
        CheckConstraint("length(trim(name)) > 0", name="pricing_adjustments_name_check"),
        Index("pricing_adjustments_menu_item", "menu_item_id"),
        Index("pricing_adjustments_org_tier", "org_id", "tier_id"),
    )


class PricingTierAddition(PricingConditions, PricingRecord, Base):
    __tablename__ = "pricing_tier_additions"
    tierId = Column("tier_id", UUID(as_uuid=True), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(String, nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    chargeUnit = Column("charge_unit", String, nullable=False)
    __table_args__ = (
        *condition_constraints("pricing_tier_additions"),
        ForeignKeyConstraint(["org_id", "tier_id"], ["pricing_tiers.org_id", "pricing_tiers.id"], ondelete="RESTRICT", name="pricing_tier_additions_tier_org_fkey"),
        CheckConstraint("amount >= 0", name="pricing_tier_additions_amount_check"),
        CheckConstraint("charge_unit IN ('guest', 'event')", name="pricing_tier_additions_unit_check"),
        CheckConstraint("length(trim(name)) > 0 AND length(trim(description)) > 0", name="pricing_tier_additions_description_check"),
        Index("pricing_tier_additions_org_tier", "org_id", "tier_id"),
    )
