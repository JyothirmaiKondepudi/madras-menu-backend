"""Quotes: the price offered to a client for one subproject (event).

Every pricing method produces the same thing: a quote with frozen lines and
the dishes it was priced for. Nothing here is recalculated from the pricing
tables afterwards; editing a rate never changes a quote already given. The
`source_table`/`source_id` on a line records which rate it came from, for
auditing only (no foreign key, so the rate can later change or be removed).

A subproject can have several quotes (one per tier offered, or revisions);
an earlier one is marked `superseded`. Accepting a quote doesn't create an
invoice by itself; `invoice_id` records the invoice made from it.
"""
import uuid

from sqlalchemy import (
    CheckConstraint, Column, Date, DateTime, ForeignKey, ForeignKeyConstraint,
    Index, Integer, Numeric, String, UniqueConstraint, func, text,
)
from sqlalchemy.dialects.postgresql import UUID

from database import Base
from models.choices import PriceWeight, QuoteLineKind, QuoteLineUnit, QuoteStatus, check_in


class Quote(Base):
    __tablename__ = "quotes"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    orgId = Column(
        "org_id", UUID(as_uuid=True),
        ForeignKey("organizations.org_id", ondelete="RESTRICT"), nullable=False,
    )
    subprojectId = Column(
        "subproject_id", UUID(as_uuid=True),
        ForeignKey("subprojects.subproject_id", ondelete="RESTRICT"), nullable=False, index=True,
    )
    pricingModelId = Column("pricing_model_id", UUID(as_uuid=True), nullable=False)
    # the tier this quote was priced at; NULL for methods without tiers
    tierId = Column("tier_id", UUID(as_uuid=True))
    status = Column(String, nullable=False, default="draft", server_default="draft")
    guestCount = Column("guest_count", Integer, nullable=False)
    currency = Column(String(3), nullable=False)
    validUntil = Column("valid_until", Date)
    discountPercent = Column("discount_percent", Numeric(5, 2), nullable=False, default=0, server_default="0")
    subtotalAmount = Column("subtotal_amount", Numeric(12, 2), nullable=False, default=0, server_default="0")
    discountAmount = Column("discount_amount", Numeric(12, 2), nullable=False, default=0, server_default="0")
    serviceChargeAmount = Column("service_charge_amount", Numeric(12, 2), nullable=False, default=0, server_default="0")
    gratuityAmount = Column("gratuity_amount", Numeric(12, 2), nullable=False, default=0, server_default="0")
    taxAmount = Column("tax_amount", Numeric(12, 2), nullable=False, default=0, server_default="0")
    totalAmount = Column("total_amount", Numeric(12, 2), nullable=False, default=0, server_default="0")
    perGuestAmount = Column("per_guest_amount", Numeric(12, 2), nullable=False, default=0, server_default="0")
    notes = Column(String)
    invoiceId = Column(
        "invoice_id", UUID(as_uuid=True), ForeignKey("invoices.invoice_id", ondelete="SET NULL"),
    )
    createdBy = Column(
        "created_by", UUID(as_uuid=True), ForeignKey("user_data.user_id", ondelete="SET NULL"),
    )
    sentAt = Column("sent_at", DateTime(timezone=True))
    acceptedAt = Column("accepted_at", DateTime(timezone=True))
    createdAt = Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now())
    updatedAt = Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    __table_args__ = (
        # the pricing version stays as long as a quote uses it
        ForeignKeyConstraint(
            ["org_id", "pricing_model_id"], ["pricing_models.org_id", "pricing_models.id"],
            ondelete="RESTRICT", name="quotes_model_org_fkey",
        ),
        ForeignKeyConstraint(
            ["org_id", "pricing_model_id", "tier_id"],
            ["pricing_tiers.org_id", "pricing_tiers.pricing_model_id", "pricing_tiers.id"],
            ondelete="RESTRICT", name="quotes_tier_fkey",
        ),
        CheckConstraint(check_in("status", QuoteStatus), name="quotes_status_check"),
        CheckConstraint("guest_count > 0", name="quotes_guest_count_check"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="quotes_currency_check"),
        CheckConstraint("discount_percent BETWEEN 0 AND 100", name="quotes_discount_check"),
        CheckConstraint(
            "subtotal_amount >= 0 AND discount_amount >= 0 AND service_charge_amount >= 0"
            " AND gratuity_amount >= 0 AND tax_amount >= 0 AND total_amount >= 0 AND per_guest_amount >= 0",
            name="quotes_amounts_check",
        ),
        CheckConstraint("status NOT IN ('sent', 'accepted') OR sent_at IS NOT NULL", name="quotes_sent_at_check"),
        CheckConstraint("status <> 'accepted' OR accepted_at IS NOT NULL", name="quotes_accepted_at_check"),
        Index("quotes_org_status", "org_id", "status"),
        Index("quotes_pricing_model", "pricing_model_id"),
        # one quote per invoice
        Index("quotes_invoice_key", "invoice_id", unique=True, postgresql_where=text("invoice_id IS NOT NULL")),
    )


class QuoteLine(Base):
    """One frozen line of a quote's price breakdown. A discount line is the
    only one with a negative amount."""

    __tablename__ = "quote_lines"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    quoteId = Column(
        "quote_id", UUID(as_uuid=True), ForeignKey("quotes.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    position = Column(Integer, nullable=False)
    kind = Column(String, nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(String)
    chargeUnit = Column("charge_unit", String, nullable=False)
    quantity = Column(Numeric(12, 2), nullable=False)
    unitPrice = Column("unit_price", Numeric(12, 2), nullable=False)
    lineTotal = Column("line_total", Numeric(12, 2), nullable=False)
    sourceTable = Column("source_table", String(63))
    sourceId = Column("source_id", UUID(as_uuid=True))
    createdAt = Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now())
    __table_args__ = (
        UniqueConstraint("quote_id", "position", name="quote_lines_quote_position_key"),
        CheckConstraint(check_in("kind", QuoteLineKind), name="quote_lines_kind_check"),
        CheckConstraint(check_in("charge_unit", QuoteLineUnit), name="quote_lines_unit_check"),
        CheckConstraint("position >= 0", name="quote_lines_position_check"),
        CheckConstraint("quantity > 0", name="quote_lines_quantity_check"),
        CheckConstraint("length(trim(name)) > 0", name="quote_lines_name_check"),
        CheckConstraint(
            "kind = 'discount' OR (unit_price >= 0 AND line_total >= 0)",
            name="quote_lines_amount_check",
        ),
        CheckConstraint("kind <> 'discount' OR line_total <= 0", name="quote_lines_discount_check"),
    )


class QuoteDish(Base):
    """A dish on the menu a quote was priced for, with its class and
    surcharge as they were then. The dish name is copied, so the quote still
    reads correctly if the catalog dish is renamed or removed."""

    __tablename__ = "quote_dishes"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    quoteId = Column(
        "quote_id", UUID(as_uuid=True), ForeignKey("quotes.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    menuItemId = Column(
        "menu_item_id", UUID(as_uuid=True), ForeignKey("menu_items.id", ondelete="SET NULL"), index=True,
    )
    position = Column(Integer, nullable=False)
    course = Column(String(50), nullable=False)
    dishName = Column("dish_name", String, nullable=False)
    priceWeight = Column("price_weight", String)
    surchargePerGuest = Column("surcharge_per_guest", Numeric(12, 2), nullable=False, default=0, server_default="0")
    createdAt = Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now())
    __table_args__ = (
        UniqueConstraint("quote_id", "position", name="quote_dishes_quote_position_key"),
        CheckConstraint(check_in("price_weight", PriceWeight), name="quote_dishes_price_weight_check"),
        CheckConstraint("position >= 0", name="quote_dishes_position_check"),
        CheckConstraint("surcharge_per_guest >= 0", name="quote_dishes_surcharge_check"),
        CheckConstraint("length(trim(course)) > 0 AND length(trim(dish_name)) > 0", name="quote_dishes_text_check"),
    )
