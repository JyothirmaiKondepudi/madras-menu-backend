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
    on a single server and there's nothing to decouple. Only flushes, same
    as create_notification: the row joins the caller's transaction and is
    saved by the route's commit, so the action and its activity row are
    saved together or not at all."""
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
    db.flush()
    db.refresh(activity)
    return activity
