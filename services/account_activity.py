from datetime import datetime, timezone

from sqlalchemy.orm import Session

from models import AccountActivity


def record_activity(
    db: Session,
    activity_type: str,
    description: str,
    project_id=None,
    subproject_id=None,
    actor_id=None,
    metadata=None,
) -> AccountActivity:
    """Called directly, in-process, from wherever a task actually completes
    (add_new_user, add_new_Project, add_new_subproject, record_payment, ...)
    — a plain function call, not a separate service/queue, since this runs
    on a single server and there's nothing to decouple. Every call is its
    own insert+commit, same as create_notification, so a caller's own
    write (already committed by the time this runs) is never rolled back
    if this one somehow failed."""
    activity = AccountActivity(
        projectId=project_id,
        subprojectId=subproject_id,
        activityType=activity_type,
        description=description,
        actorId=actor_id,
        occurredAt=datetime.now(timezone.utc),
        activityMetadata=metadata,
    )
    db.add(activity)
    db.commit()
    db.refresh(activity)
    return activity
