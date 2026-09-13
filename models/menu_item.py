from sqlalchemy import Column, String, DateTime, Boolean, Numeric, ForeignKey, ARRAY, func
from datetime import datetime
import uuid
from database import Base

# --- Ported from madras-menu-studio's Prisma schema (owned there, not by this
# repo's Alembic migrations) — mapped read/write against the existing table,
# matching its real column types (text ids, not UUID) exactly. ---


class MenuItem(Base):
    __tablename__ = 'menu_items'

    id = Column("id", String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column("name", String, nullable=False, unique=True)
    course = Column("course", String, nullable=False)
    vegNonveg = Column("veg_nonveg", String, nullable=False)
    cuisineTags = Column("cuisine_tags", ARRAY(String))
    priceWeight = Column("price_weight", String, nullable=False)
    isStaple = Column("is_staple", Boolean, nullable=False, default=False)
    servedAsLiveStation = Column("served_as_live_station", Boolean, nullable=False, default=False)
    allergens = Column("allergens", ARRAY(String))
    dietaryFlags = Column("dietary_flags", ARRAY(String))
    religionSuitability = Column("religion_suitability", ARRAY(String))
    occasionSuitability = Column("occasion_suitability", ARRAY(String))
    spiceLevel = Column("spice_level", String)
    prepMethod = Column("prep_method", String)
    portionUnit = Column("portion_unit", String)
    costPerPerson = Column("cost_per_person", Numeric(8, 2))
    taxCategoryId = Column("tax_category_id", String, ForeignKey('tax_categories.id'))
    active = Column("active", Boolean, nullable=False, default=True)
    confidence = Column("confidence", String)
    sourceDocs = Column("source_docs", ARRAY(String))
    createdAt = Column("created_at", DateTime, default=datetime.now, server_default=func.now(), nullable=False)
    updatedAt = Column("updated_at", DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)
