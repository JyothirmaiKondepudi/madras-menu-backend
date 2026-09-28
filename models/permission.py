from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
import uuid
from database import Base


class Permission(Base):
    """A single granular action, e.g. 'project:create', 'invoice:view_all'."""
    __tablename__ = 'permissions'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, unique=True, nullable=False)
    description = Column(String, nullable=True)


class RolePermission(Base):
    """Maps a role name (matching User.userRole's string values, e.g. 'vendor')
    to a permission."""
    __tablename__ = 'role_permissions'

    role = Column(String, primary_key=True)
    permissionId = Column("permission_id", UUID(as_uuid=True), ForeignKey('permissions.id'), primary_key=True)
