"""A project's activity timeline (BE-14): account_activity rows and payment
events from billing_history, merged into one list, newest first.

Payments aren't written to account_activity (they already have their own
table, and Stripe payments will arrive there without going through this app's
services), so the two are combined at read time with UNION ALL. That keeps
paging correct across both: a page is cut from the merged list, not from
each table separately.
"""

from datetime import datetime, timezone

from sqlalchemy import Select, String, literal, null, select, union_all
from sqlalchemy.orm import Session

from models import AccountActivity, BillingHistory, Invoice, Project
from services.account_activity import record_activity
from services.timezones import effective_timezone, to_instant

PAYMENT_LABELS = {
    "Payment_Succeeded": "Payment received",
    "Payment_Declined": "Payment declined",
    "Payment_Pending": "Payment pending",
    "Refund_Initiated": "Refund started",
    "Refund_Issued": "Refund issued",
}


def project_timeline_query(project_id) -> Select:
    activity = select(
        AccountActivity.id.label("id"),
        literal("activity", String).label("kind"),
        AccountActivity.activityType.label("type"),
        AccountActivity.description.label("description"),
        AccountActivity.occurredAt.label("occurredAt"),
        AccountActivity.actorId.label("actorId"),
        AccountActivity.subprojectId.label("subprojectId"),
        null().label("amount"),
        null().label("voidedAt"),
    ).where(AccountActivity.projectId == project_id)

    payments = (
        select(
            BillingHistory.id.label("id"),
            literal("payment", String).label("kind"),
            BillingHistory.eventType.label("type"),
            null().label("description"),
            BillingHistory.occurredAt.label("occurredAt"),
            null().label("actorId"),
            Invoice.subprojectId.label("subprojectId"),
            BillingHistory.amount.label("amount"),
            BillingHistory.voidedAt.label("voidedAt"),
        )
        .join(Invoice, BillingHistory.invoiceId == Invoice.invoiceId)
        .where(
            Invoice.projectAssociatedTo == project_id,
            # the global soft-delete filter (database.py) already hides these;
            # stated here too so the rule is visible where the timeline is built
            Invoice.invoiceDeletedAt.is_(None),
        )
    )

    merged = union_all(activity, payments).subquery("timeline")
    return select(merged)


def describe_payment(entry: dict) -> dict:
    """Payment rows have no stored description; build one for display."""
    if entry["kind"] != "payment":
        return entry
    label = PAYMENT_LABELS.get(entry["type"], entry["type"])
    text = f"{label}: ${entry['amount']:,.2f}"
    if entry["voidedAt"] is not None:
        text += " (voided)"
    return {**entry, "description": text}


def record_follow_up(
    project: Project, note: str, next_follow_up_at: datetime | None, db: Session, actor_id
) -> Project:
    """Logs a follow-up on the timeline and moves the project's follow-up
    dates: last = now, next = what the vendor scheduled (None clears it)."""
    now = datetime.now(timezone.utc)
    if next_follow_up_at is not None:
        next_follow_up_at = to_instant(next_follow_up_at, effective_timezone(project))
    project.lastFollowedUpAt = now
    project.nextFollowUpAt = next_follow_up_at
    record_activity(
        db,
        activity_type="followed_up",
        description=f"Followed up: {note}",
        project_id=project.projectId,
        actor_id=actor_id,
        metadata={
            "note": note,
            "nextFollowUpAt": next_follow_up_at.isoformat() if next_follow_up_at else None,
        },
    )
    db.flush()
    db.refresh(project)
    return project
