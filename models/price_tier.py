from sqlalchemy import Column, String, Numeric, UUID
import uuid
from database import Base


class PriceTier(Base):
    __tablename__ = "price_tiers"

    id = Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column("name", String, nullable=False)
    occasionType = Column("occasion_type", String, nullable=False)
    serviceStyle = Column("service_style", String, nullable=False)
    basePerPerson = Column("base_per_person", Numeric(8, 2), nullable=False)
