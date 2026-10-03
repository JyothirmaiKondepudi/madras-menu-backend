from sqlalchemy import Column, String, Numeric, ARRAY, text
import uuid
from database import Base


class LiveStation(Base):
    __tablename__ = 'live_stations'

    id = Column("id", String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column("name", String, nullable=False)
    region = Column("region", String, nullable=False)
    vegNonveg = Column("veg_nonveg", String, nullable=False)
    pricePerPerson = Column("price_per_person", Numeric(8, 2), nullable=False)
    equipmentNeeded = Column("equipment_needed", ARRAY(String), server_default=text("'{}'"))
