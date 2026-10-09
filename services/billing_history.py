from datetime import datetime, timezone

from models import BillingHistory, BillingInfo, Invoice, Project, Subproject
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from services.account_activity import record_activity


def count_live_payments(invoice_id, db: Session) -> int:
    """Successful payments on an invoice that haven't been voided — the ones
    that still count as money received. Declined or pending attempts never
    moved money, so they don't count."""
    return db.scalar(
        select(func.count())
        .select_from(BillingHistory)
        .where(
            BillingHistory.invoiceId == invoice_id,
            BillingHistory.eventType == "Payment_Succeeded",
            BillingHistory.voidedAt.is_(None),
        )
    )


def get_billing_history_by_id(billing_history_id, db: Session):
    return db.get(BillingHistory, billing_history_id)


def get_billing_history_by_invoice_id(invoice_id, db: Session):
    return (
        db.execute(
            select(BillingHistory)
            .where(BillingHistory.invoiceId == invoice_id)
            .order_by(BillingHistory.occurredAt.desc())
        )
        .scalars()
        .all()
    )


def get_billing_history_by_subproject_id(subproject_id, db: Session):
    return (
        db.execute(
            select(BillingHistory)
            .join(Invoice, BillingHistory.invoiceId == Invoice.invoiceId)
            .where(Invoice.subprojectId == subproject_id)
            .order_by(BillingHistory.occurredAt.desc())
        )
        .scalars()
        .all()
    )


def get_all_billing_history(organization_id, db: Session):
    """Every transaction in the caller's org. A payment's org is its
    invoice's project's org, so scope by joining through both."""
    return (
        db.execute(
            select(BillingHistory)
            .join(Invoice, BillingHistory.invoiceId == Invoice.invoiceId)
            .join(Project, Invoice.projectAssociatedTo == Project.projectId)
            .where(Project.organizationId == organization_id)
            .order_by(BillingHistory.occurredAt.desc())
        )
        .scalars()
        .all()
    )


def get_billing_history_by_project_ids(project_ids, db: Session):
    """For a non-vendor's GET /billing-history — every transaction billed
    against a subproject belonging to any project they're linked to, the
    same scoping rule services/subproject.py's get_subprojects_by_project_ids
    already uses."""
    return (
        db.execute(
            select(BillingHistory)
            .join(Invoice, BillingHistory.invoiceId == Invoice.invoiceId)
            .join(Subproject, Invoice.subprojectId == Subproject.subprojectId)
            .where(Subproject.projectAssociatedTo.in_(project_ids))
            .order_by(BillingHistory.occurredAt.desc())
        )
        .scalars()
        .all()
    )


def _recompute_billing_info(subproject_id, db: Session) -> None:
    """billing_info is a derived summary of billing_history, not
    independently maintained state — recomputed from the actual rows every
    time, rather than incrementally adjusted, so it can never drift out of
    sync with the log it's summarizing.

    Every amount involved is Numeric dollars, so the sums are exact and need
    no unit conversion.

    Locks the billing_info row first, held until the caller commits, so two
    recomputes for the same subproject run one after the other. Without it,
    two payments arriving together each sum without the other's row and the
    last commit wins with a total missing one payment. The row is created
    first if it's missing, since a row that doesn't exist can't be locked.
    """
    # make sure the row exists, then lock it. If another request is
    # inserting it at the same moment, ON CONFLICT waits for that one to
    # commit and then skips, so both end up locking the same row. The zeros
    # are placeholders for the NOT NULL columns, overwritten below.
    db.execute(
        insert(BillingInfo)
        .values(
            subprojectId=subproject_id,
            totalInvoiced=0,
            totalPaid=0,
            totalRefunded=0,
            balanceDue=0,
            status="payment_pending",
            lastEventAt=datetime.now(timezone.utc),
        )
        .on_conflict_do_nothing(index_elements=[BillingInfo.subprojectId])
    )
    info = db.execute(
        select(BillingInfo)
        .where(BillingInfo.subprojectId == subproject_id)
        .with_for_update()
    ).scalar_one()

    total_invoiced = db.execute(
        select(func.coalesce(func.sum(Invoice.invoiceAmount), 0)).where(
            Invoice.subprojectId == subproject_id,
            Invoice.invoiceDeletedAt.is_(None),
        )
    ).scalar_one()

    total_paid = db.execute(
        select(func.coalesce(func.sum(BillingHistory.amount), 0))
        .join(Invoice, BillingHistory.invoiceId == Invoice.invoiceId)
        .where(
            Invoice.subprojectId == subproject_id,
            BillingHistory.eventType == "Payment_Succeeded",
            BillingHistory.voidedAt.is_(None),
        )
    ).scalar_one()
    total_refunded = db.execute(
        select(func.coalesce(func.sum(BillingHistory.amount), 0))
        .join(Invoice, BillingHistory.invoiceId == Invoice.invoiceId)
        .where(
            Invoice.subprojectId == subproject_id,
            BillingHistory.eventType == "Refund_Issued",
            BillingHistory.voidedAt.is_(None),
        )
    ).scalar_one()

    balance_due = total_invoiced - total_paid + total_refunded

    if balance_due <= 0:
        status = "paid_in_full"
    elif total_paid > 0:
        status = "partial_payment_received"
    else:
        status = "payment_pending"

    info.totalInvoiced = total_invoiced
    info.totalPaid = total_paid
    info.totalRefunded = total_refunded
    info.balanceDue = balance_due
    info.status = status
    info.lastEventAt = datetime.now(timezone.utc)


def record_payment(
    invoice: Invoice, amount: int, occurred_at, billing_metadata, db: Session
) -> BillingHistory:
    """The one place a "payment made" billing_history row gets written —
    always source="Manual" and eventType="Payment_Succeeded", since this is
    the vendor manually recording an offline payment (cash, check, bank
    transfer), not a Stripe webhook. Updates billing_info in the same
    transaction so the summary is never momentarily out of sync with the
    log that produced it."""
    entry = BillingHistory(
        invoiceId=invoice.invoiceId,
        eventType="Payment_Succeeded",
        amount=amount,
        occurredAt=occurred_at or datetime.now(timezone.utc),
        source="Manual",
        billingMetadata=billing_metadata,
    )
    db.add(entry)

    if invoice.subprojectId is not None:
        db.flush()  # so the SUM query below sees this row
        _recompute_billing_info(invoice.subprojectId, db)

    db.commit()
    db.refresh(entry)
    return entry


def void_payment(
    payment: BillingHistory, invoice: Invoice, reason: str, db: Session, actor_id=None
) -> BillingHistory:
    """Marks a payment recorded by mistake as void. The row stays in the
    history; it just stops counting toward the billing totals. The route has
    already checked that the payment can be voided."""
    payment.voidedAt = datetime.now(timezone.utc)
    payment.voidedReason = reason

    if invoice.subprojectId is not None:
        db.flush()  # so the recompute leaves this payment out
        _recompute_billing_info(invoice.subprojectId, db)

    db.commit()
    db.refresh(payment)
    record_activity(
        db,
        activity_type="payment_voided",
        description=(
            f'Payment of ${payment.amount:,.2f} for "{invoice.project.projectName}" '
            f"was voided: {reason}"
        ),
        project_id=invoice.projectAssociatedTo,
        subproject_id=invoice.subprojectId,
        actor_id=actor_id,
    )
    return payment
