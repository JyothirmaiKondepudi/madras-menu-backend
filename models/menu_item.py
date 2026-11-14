from sqlalchemy import (
    Column,
    String,
    DateTime,
    Boolean,
    Numeric,
    UUID,
    ForeignKey,
    ARRAY,
    UniqueConstraint,
    func,
    text,
)
import uuid
from database import Base


class MenuItem(Base):
    """A dish in one caterer's catalog. Each organization has its own dishes;
    routes only ever read or change the caller's organization's dishes."""

    __tablename__ = "menu_items"
    __table_args__ = (
        # names are unique per caterer, not across the app
        UniqueConstraint("org_id", "name", name="menu_items_org_name_key"),
        # target for composite foreign keys (item_relationships) that keep a
        # link between two dishes inside one caterer's catalog
        UniqueConstraint("org_id", "id", name="menu_items_org_item_key"),
    )

    id = Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    orgId = Column(
        "org_id",
        UUID(as_uuid=True),
        ForeignKey("organizations.org_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name = Column("name", String, nullable=False)
    course = Column("course", String, nullable=False)
    vegNonveg = Column("veg_nonveg", String, nullable=False)
    cuisineTags = Column("cuisine_tags", ARRAY(String))
    priceWeight = Column("price_weight", String, nullable=False)
    isStaple = Column(
        "is_staple",
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    servedAsLiveStation = Column(
        "served_as_live_station",
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    allergens = Column("allergens", ARRAY(String), server_default=text("'{}'"))
    dietaryFlags = Column("dietary_flags", ARRAY(String), server_default=text("'{}'"))
    religionSuitability = Column(
        "religion_suitability", ARRAY(String), server_default=text("'{}'")
    )
    occasionSuitability = Column(
        "occasion_suitability", ARRAY(String), server_default=text("'{}'")
    )
    spiceLevel = Column("spice_level", String)
    prepMethod = Column("prep_method", String)
    portionUnit = Column("portion_unit", String)
    costPerPerson = Column("cost_per_person", Numeric(8, 2))
    taxCategoryId = Column(
        "tax_category_id",
        UUID(as_uuid=True),
        ForeignKey("tax_categories.id", onupdate="CASCADE", ondelete="SET NULL"),
        index=True,
    )
    active = Column(
        "active", Boolean, nullable=False, default=True, server_default=text("true")
    )
    confidence = Column("confidence", String)
    sourceDocs = Column("source_docs", ARRAY(String), server_default=text("'{}'"))
    createdAt = Column(
        "created_at", DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updatedAt = Column(
        "updated_at",
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
