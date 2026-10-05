from sqlalchemy import (
    Column,
    String,
    DateTime,
    Boolean,
    Numeric,
    ForeignKey,
    ARRAY,
    func,
    text,
)
import uuid
from database import Base


class MenuItem(Base):
    __tablename__ = "menu_items"

    id = Column("id", String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column("name", String, nullable=False, unique=True)
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
        String,
        ForeignKey("tax_categories.id", onupdate="CASCADE", ondelete="SET NULL"),
        index=True,
    )
    active = Column(
        "active", Boolean, nullable=False, default=True, server_default=text("true")
    )
    confidence = Column("confidence", String)
    sourceDocs = Column("source_docs", ARRAY(String), server_default=text("'{}'"))
    createdAt = Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False)
    updatedAt = Column(
        "updated_at",
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
