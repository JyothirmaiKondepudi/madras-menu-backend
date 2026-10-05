from sqlalchemy import Column, String, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid
from database import Base


class AccountActivity(Base):
    """Project-lifecycle timeline (project/subproject created, menu
    generated, invoice generated, ...). Payment events live in
    billing_history and are merged in at read time.
    """

    __tablename__ = "account_activity"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # FKs cascade: activity rows are derived and must never block deletes.
    # Nullable for "user created" events, which have no project yet.
    projectId = Column(
        "project_id",
        UUID(as_uuid=True),
        ForeignKey("projects.project_id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    # Null for project-level events.
    subprojectId = Column(
        "subproject_id",
        UUID(as_uuid=True),
        ForeignKey("subprojects.subproject_id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    # Plain string, not an enum, so new types don't need a migration.
    activityType = Column("activity_type", String, nullable=False)
    description = Column("description", String, nullable=False)
    # Null for system-triggered events.
    actorId = Column(
        "actor_id",
        UUID(as_uuid=True),
        ForeignKey("user_data.user_id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    occurredAt = Column("occurred_at", DateTime(timezone=True), nullable=False)
    # "metadata" is reserved by SQLAlchemy.
    activityMetadata = Column("metadata", JSONB)
