from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid
from database import Base


class AccountActivity(Base):
    """One row per project-lifecycle milestone (project created, subproject
    created, menu generated, changes suggested, invoice generated,
    renegotiated, ...) — the general-purpose timeline behind a project's
    activity stepper. Deliberately does NOT include payment events —
    billing_history stays the single source of truth for those, merged in
    at read time, rather than duplicating payment rows into a second log.
    """
    __tablename__ = 'account_activity'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Every FK here cascades on delete, deliberately: an activity row is an
    # ephemeral, derived record (like Notification), never something that
    # should block deleting the project/subproject/user it's about. Caught
    # for real by the test suite — deleting a project failed with a 409
    # the moment an activity row referenced it, before this was added.
    #
    # Nullable: a "user created" event has no project yet (a user can exist
    # before ever being linked to one) — every other event type always
    # sets this.
    projectId = Column("project_id", UUID(as_uuid=True), ForeignKey('projects.project_id', ondelete="CASCADE"), nullable=True)
    # Null for project-level events (e.g. "project created"); set for
    # events specific to one subproject (e.g. "Mehendi subproject created").
    subprojectId = Column("subproject_id", UUID(as_uuid=True), ForeignKey('subprojects.subproject_id', ondelete="CASCADE"), nullable=True)
    # Plain string, not a Postgres enum — new milestone types (e.g. once
    # menu generation actually ships) shouldn't need an ALTER TYPE
    # migration, same reasoning as Notification.type / BillingHistory.eventType.
    activityType = Column("activity_type", String, nullable=False)
    description = Column("description", String, nullable=False)
    # Who did this — null where there's no clear actor (e.g. a system-
    # triggered event with nobody directly behind it).
    actorId = Column("actor_id", UUID(as_uuid=True), ForeignKey('user_data.user_id', ondelete="CASCADE"), nullable=True)
    occurredAt = Column("occurred_at", DateTime, nullable=False)
    # Not "metadata" — that attribute name is reserved by SQLAlchemy's
    # Declarative API. Same fix as BillingHistory.billingMetadata.
    activityMetadata = Column('metadata', JSONB)
