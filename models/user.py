from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid
from database import Base


class User(Base):
    __tablename__ = 'user_data'

    userId = Column('user_id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fullName = Column("full_name", String, nullable=False)
    userEmail = Column("email", String, unique=True, nullable=False)
    userPhoneNumber = Column("phone_number", String(10), nullable=False)
    preferredContact = Column("preferred_contact", String, nullable=False)
    userAddress = Column("address", String)
    userRole = Column('role', String, nullable=False)
    userCreatedAt = Column("created_at", DateTime, default=datetime.now)
    updatedAt = Column("updated_at", DateTime, default=datetime.now, onupdate=datetime.now)
