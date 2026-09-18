from sqlalchemy import Column, String, DateTime, Numeric, func
from datetime import datetime
import uuid
from database import Base

# --- Ported from madras-menu-studio's Prisma schema (owned there, not by this
# repo's Alembic migrations) — mapped read/write against the existing table,
# matching its real column types (text ids, not UUID) exactly. ---


class TaxCategory(Base):
    __tablename__ = 'tax_categories'

    id = Column("id", String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column("name", String, nullable=False, unique=True)
    jurisdiction = Column("jurisdiction", String, nullable=False)
    ratePercent = Column("rate_percent", Numeric(5, 3), nullable=False)
    effectiveDate = Column("effective_date", DateTime, default=datetime.now, server_default=func.now(), nullable=False)
