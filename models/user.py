from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
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
    # Null means this user has never had a password set (e.g. a client row
    # a vendor created but hasn't given login access to yet) — not every
    # user_data row is expected to be able to log in.
    passwordHash = Column("password_hash", String, nullable=True)
    # Who created this row (a vendor, via POST /users) — null for the one
    # bootstrap vendor, who was inserted directly against the database, not
    # through the API. Used to notify "the one who sent this invite" when
    # a new user is created (see notifications/service.py).
    createdBy = Column("created_by", UUID(as_uuid=True), ForeignKey('user_data.user_id'), nullable=True)
    userCreatedAt = Column("created_at", DateTime, default=datetime.now)
    updatedAt = Column("updated_at", DateTime, default=datetime.now, onupdate=datetime.now)

    projects = relationship('Project', secondary='user_projects', back_populates='users')
