"""A caterer's live cooking stations: an add-on catalog priced per guest.

Owned by one organization, like the rate card and equipment list. Any
pricing method can add a station to a quote; the quote copies its price, so
editing a station never changes a quote already given. `scripts/import_live_stations.py`
loads a caterer's list from a CSV file.
"""
import uuid

from sqlalchemy import (
    ARRAY, Boolean, CheckConstraint, Column, DateTime, ForeignKey, Index,
    Integer, Numeric, String, UUID, func, text,
)

from database import Base
from models.choices import LiveStationDiet, check_in


class LiveStation(Base):
    __tablename__ = "live_stations"
    __table_args__ = (
        CheckConstraint(check_in("veg_nonveg", LiveStationDiet), name="live_stations_veg_nonveg_check"),
        CheckConstraint("price_per_person >= 0", name="live_stations_price_check"),
        CheckConstraint("min_guests > 0", name="live_stations_min_guests_check"),
        CheckConstraint("length(trim(name)) > 0", name="live_stations_name_check"),
        # one station per name per caterer, ignoring case, so an import can update it
        Index("live_stations_org_name_key", "org_id", func.lower(text("name")), unique=True),
    )

    id = Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    orgId = Column(
        "org_id", UUID(as_uuid=True),
        ForeignKey("organizations.org_id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    name = Column("name", String, nullable=False)
    # cuisine tag, e.g. "north_indian" (same tags as menu_items.cuisine_tags)
    region = Column("region", String, nullable=False)
    vegNonveg = Column("veg_nonveg", String, nullable=False)
    description = Column("description", String)
    pricePerPerson = Column("price_per_person", Numeric(12, 2), nullable=False)
    minGuests = Column("min_guests", Integer, nullable=False, default=1, server_default="1")
    equipmentNeeded = Column(
        "equipment_needed", ARRAY(String), nullable=False, server_default=text("'{}'"), default=list,
    )
    active = Column("active", Boolean, nullable=False, default=True, server_default=text("true"))
    createdAt = Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now())
    updatedAt = Column(
        "updated_at", DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now(),
    )
