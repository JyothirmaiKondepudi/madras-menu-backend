from sqlalchemy import Column, String, DateTime, Numeric, func, UUID
import uuid
from database import Base


class TaxCategory(Base):
    __tablename__ = "tax_categories"

    id = Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column("name", String, nullable=False, unique=True)
    jurisdiction = Column("jurisdiction", String, nullable=False)
    ratePercent = Column("rate_percent", Numeric(5, 3), nullable=False)
    effectiveDate = Column(
        "effective_date",
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
