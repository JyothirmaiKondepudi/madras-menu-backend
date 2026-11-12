"""Organization-owned catering prices, independent of menu generation.

Every caterer prices through a *pricing model*: one row in `pricing_models`
naming a pricing method (today only `tiered_per_guest`, Madras's method) and a
version. A method is a calculator in code; its configuration lives in tables
that all hang off the model, so a new version is a new set of rows and a quote
can point at the exact version it was priced with. Adding a caterer whose
pricing works the same way is data only; a genuinely different way of pricing
is a new method (code plus its own configuration tables).

`tiered_per_guest` configuration:
- tiers (Elegant, Premium, ...), each with course slots (`pricing_tier_courses`):
  how many dishes of each course the tier includes and which dish classes its
  base price covers. The dishes themselves change for every event; the slots
  don't.
- base rates per guest, with a minimum charge.
- tier additions: explicit extras a higher tier adds to the base package.
- adjustments: conditional surcharges, optionally per tier, per dish, or per
  dish class (`price_weight`).
- one policy row: service charge, gratuity, tax mode, rounding, deposit, how
  long a quote stays valid.

NULL conditions are wildcards. Matching/overlap resolution belongs to the
pricing calculator, not to this storage model. Quotes (`models/quote.py`)
store a frozen copy of every price they used.
"""
import uuid

from sqlalchemy import (
    ARRAY, Boolean, CheckConstraint, Column, Date, DateTime, ForeignKey,
    ForeignKeyConstraint, Index, Integer, Numeric, String, UniqueConstraint,
    func, text,
)
from sqlalchemy.dialects.postgresql import UUID

from database import Base
from models.choices import (
    Diet, EventType, PriceWeight, PricingMethod, PricingModelStatus,
    ServiceStyle, TaxMode, check_all_in, check_in,
)


def _model_fk(table):
    """Config rows belong to a pricing model of the same organization."""
    return ForeignKeyConstraint(
        ["org_id", "pricing_model_id"], ["pricing_models.org_id", "pricing_models.id"],
        ondelete="CASCADE", name=f"{table}_model_org_fkey",
    )


def _tier_fk(table):
    """A tier reference must stay inside the same organization and model."""
    return ForeignKeyConstraint(
        ["org_id", "pricing_model_id", "tier_id"],
        ["pricing_tiers.org_id", "pricing_tiers.pricing_model_id", "pricing_tiers.id"],
        ondelete="CASCADE", name=f"{table}_tier_fkey",
    )


class PricingModel(Base):
    __tablename__ = "pricing_models"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    orgId = Column(
        "org_id", UUID(as_uuid=True),
        ForeignKey("organizations.org_id", ondelete="RESTRICT"), nullable=False,
    )
    method = Column(String, nullable=False)
    version = Column(Integer, nullable=False)
    status = Column(String, nullable=False, default="draft", server_default="draft")
    name = Column(String(100), nullable=False)
    notes = Column(String)
    publishedAt = Column("published_at", DateTime(timezone=True))
    createdAt = Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now())
    updatedAt = Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    __table_args__ = (
        UniqueConstraint("org_id", "id", name="pricing_models_org_id_id_key"),
        UniqueConstraint("org_id", "version", name="pricing_models_org_version_key"),
        CheckConstraint(check_in("method", PricingMethod), name="pricing_models_method_check"),
        CheckConstraint(check_in("status", PricingModelStatus), name="pricing_models_status_check"),
        CheckConstraint("version > 0", name="pricing_models_version_check"),
        CheckConstraint("length(trim(name)) > 0", name="pricing_models_name_check"),
        CheckConstraint("status = 'draft' OR published_at IS NOT NULL", name="pricing_models_published_at_check"),
        # quotes are priced with the one published version
        Index("pricing_models_one_published", "org_id", unique=True,
              postgresql_where=text("status = 'published'")),
    )


class PricingRecord:
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    orgId = Column(
        "org_id", UUID(as_uuid=True),
        ForeignKey("organizations.org_id", ondelete="RESTRICT"), nullable=False,
    )
    pricingModelId = Column("pricing_model_id", UUID(as_uuid=True), nullable=False)
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
        _model_fk("pricing_tiers"),
        UniqueConstraint("org_id", "pricing_model_id", "id", name="pricing_tiers_org_model_id_key"),
        UniqueConstraint("pricing_model_id", "position", name="pricing_tiers_model_position_key"),
        CheckConstraint("position >= 0", name="pricing_tiers_position_check"),
        CheckConstraint("length(trim(name)) > 0", name="pricing_tiers_name_check"),
        Index("pricing_tiers_model_name_key", "pricing_model_id", func.lower(name), unique=True),
        Index("pricing_tiers_one_active_base", "pricing_model_id", unique=True,
              postgresql_where=text("is_base AND active")),
    )


class PricingTierCourse(Base):
    """One course slot of a tier: how many dishes of this course the tier
    includes, and which dish classes its base price covers. A dish of any
    other class fills the slot at a surcharge (an adjustment with that
    price_weight). `course` uses the same values as menu_items.course."""

    __tablename__ = "pricing_tier_courses"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    orgId = Column(
        "org_id", UUID(as_uuid=True),
        ForeignKey("organizations.org_id", ondelete="RESTRICT"), nullable=False,
    )
    pricingModelId = Column("pricing_model_id", UUID(as_uuid=True), nullable=False)
    tierId = Column("tier_id", UUID(as_uuid=True), nullable=False)
    course = Column(String(50), nullable=False)
    dishCount = Column("dish_count", Integer, nullable=False)
    includedPriceWeights = Column(
        "included_price_weights", ARRAY(String), nullable=False,
        server_default=text("'{}'"), default=list,
    )
    position = Column(Integer, nullable=False, default=0, server_default="0")
    createdAt = Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now())
    updatedAt = Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    __table_args__ = (
        _model_fk("pricing_tier_courses"),
        _tier_fk("pricing_tier_courses"),
        CheckConstraint("dish_count > 0", name="pricing_tier_courses_dish_count_check"),
        CheckConstraint("position >= 0", name="pricing_tier_courses_position_check"),
        CheckConstraint("length(trim(course)) > 0", name="pricing_tier_courses_course_check"),
        CheckConstraint(check_all_in("included_price_weights", PriceWeight),
                        name="pricing_tier_courses_price_weights_check"),
        Index("pricing_tier_courses_tier_course_key", "tier_id", func.lower(course), unique=True),
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
        _model_fk(name),
        CheckConstraint(check_in("event_type", EventType), name=f"{name}_event_check"),
        CheckConstraint(check_in("service_style", ServiceStyle), name=f"{name}_style_check"),
        CheckConstraint(check_in("diet", Diet), name=f"{name}_diet_check"),
        CheckConstraint("min_guests > 0 AND (max_guests IS NULL OR max_guests >= min_guests)", name=f"{name}_guests_check"),
        CheckConstraint("effective_until IS NULL OR effective_until > effective_from", name=f"{name}_dates_check"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name=f"{name}_currency_check"),
        Index(f"{name}_model_lookup", "pricing_model_id", "active", "currency", "effective_from"),
    )


class PricingBaseRate(PricingConditions, PricingRecord, Base):
    __tablename__ = "pricing_base_rates"
    name = Column(String(100), nullable=False)
    pricePerPerson = Column("price_per_person", Numeric(12, 2), nullable=False)
    minimumCharge = Column("minimum_charge", Numeric(12, 2), nullable=False, default=0, server_default="0")
    # Display text for proposals; the executable rules are pricing_tier_courses.
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
    # Optional dish class: a surcharge for every dish of this class that a
    # tier's course slot doesn't cover. Exclusive with menu_item_id.
    priceWeight = Column("price_weight", String)
    amount = Column(Numeric(12, 2), nullable=False)
    chargeUnit = Column("charge_unit", String, nullable=False)
    __table_args__ = (
        *condition_constraints("pricing_adjustments"),
        _tier_fk("pricing_adjustments"),
        CheckConstraint("amount >= 0", name="pricing_adjustments_amount_check"),
        CheckConstraint("charge_unit IN ('guest', 'event')", name="pricing_adjustments_unit_check"),
        CheckConstraint("length(trim(name)) > 0", name="pricing_adjustments_name_check"),
        CheckConstraint(check_in("price_weight", PriceWeight), name="pricing_adjustments_price_weight_check"),
        CheckConstraint("menu_item_id IS NULL OR price_weight IS NULL", name="pricing_adjustments_dish_or_class_check"),
        Index("pricing_adjustments_menu_item", "menu_item_id"),
        Index("pricing_adjustments_model_tier", "pricing_model_id", "tier_id"),
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
        _tier_fk("pricing_tier_additions"),
        CheckConstraint("amount >= 0", name="pricing_tier_additions_amount_check"),
        CheckConstraint("charge_unit IN ('guest', 'event')", name="pricing_tier_additions_unit_check"),
        CheckConstraint("length(trim(name)) > 0 AND length(trim(description)) > 0", name="pricing_tier_additions_description_check"),
        Index("pricing_tier_additions_model_tier", "pricing_model_id", "tier_id"),
    )


class PricingPolicy(Base):
    """The model-wide rules applied after the line items: one row per model."""

    __tablename__ = "pricing_policies"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    orgId = Column(
        "org_id", UUID(as_uuid=True),
        ForeignKey("organizations.org_id", ondelete="RESTRICT"), nullable=False,
    )
    pricingModelId = Column("pricing_model_id", UUID(as_uuid=True), nullable=False, unique=True)
    currency = Column(String(3), nullable=False)
    serviceChargePercent = Column("service_charge_percent", Numeric(5, 2), nullable=False, default=0, server_default="0")
    gratuityPercent = Column("gratuity_percent", Numeric(5, 2), nullable=False, default=0, server_default="0")
    taxMode = Column("tax_mode", String, nullable=False, default="per_dish_category", server_default="per_dish_category")
    flatTaxPercent = Column("flat_tax_percent", Numeric(6, 3))
    # e.g. 0.25 rounds the per-guest price to the nearest 25 cents
    roundingIncrement = Column("rounding_increment", Numeric(8, 2), nullable=False, default=0.01, server_default="0.01")
    depositPercent = Column("deposit_percent", Numeric(5, 2), nullable=False, default=0, server_default="0")
    quoteValidDays = Column("quote_valid_days", Integer, nullable=False, default=30, server_default="30")
    createdAt = Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now())
    updatedAt = Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    __table_args__ = (
        _model_fk("pricing_policies"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="pricing_policies_currency_check"),
        CheckConstraint(check_in("tax_mode", TaxMode), name="pricing_policies_tax_mode_check"),
        CheckConstraint(
            "service_charge_percent BETWEEN 0 AND 100 AND gratuity_percent BETWEEN 0 AND 100"
            " AND deposit_percent BETWEEN 0 AND 100",
            name="pricing_policies_percent_check",
        ),
        CheckConstraint(
            "(tax_mode = 'flat_rate') = (flat_tax_percent IS NOT NULL)"
            " AND (flat_tax_percent IS NULL OR flat_tax_percent BETWEEN 0 AND 100)",
            name="pricing_policies_flat_tax_check",
        ),
        CheckConstraint("rounding_increment > 0", name="pricing_policies_rounding_check"),
        CheckConstraint("quote_valid_days > 0", name="pricing_policies_valid_days_check"),
    )
