from sqlalchemy import Column, String, Numeric, ARRAY, text, UUID
import uuid
from database import Base


class LiveStation(Base):
    __tablename__ = "live_stations"

    id = Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column("name", String, nullable=False)
    region = Column("region", String, nullable=False)
    vegNonveg = Column("veg_nonveg", String, nullable=False)
    pricePerPerson = Column("price_per_person", Numeric(8, 2), nullable=False)
    equipmentNeeded = Column(
        "equipment_needed", ARRAY(String), server_default=text("'{}'")
    )
