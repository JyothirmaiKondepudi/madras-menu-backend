from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
import uuid
from database import Base


class Permission(Base):
    """A single granular action — 'project:create', 'invoice:view_all',
    etc. Deliberately fine-grained (one row per resource+action) rather
    than a handful of broad buckets, since the whole point of this table
    is to let a future role get a genuinely different subset of capabilities
    than vendor, not just less than vendor.\""""
    __tablename__ = 'permissions'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, unique=True, nullable=False)
    description = Column(String, nullable=True)


class RolePermission(Base):
    """Maps a role NAME (matching the plain-string values User.userRole
    already uses — 'vendor', 'client') to a permission. Keyed by role
    string rather than a foreign key to a separate `roles` table, since
    roles aren't independent entities with their own attributes here,
    just labels — introducing a `roles` table would be a bigger, riskier
    change to User.userRole than this feature calls for."""
    __tablename__ = 'role_permissions'

    role = Column(String, primary_key=True)
    permissionId = Column("permission_id", UUID(as_uuid=True), ForeignKey('permissions.id'), primary_key=True)
