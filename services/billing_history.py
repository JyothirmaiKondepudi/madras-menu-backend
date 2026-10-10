from datetime import datetime, timezone

from models import BillingHistory, BillingInfo, Invoice, Project, Subproject
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from services.account_activity import record_activity
from services.invoice_status import (
    COUNTED_INVOICE_STATUSES,
    EDITABLE_INVOICE_STATUSES,
    change_invoice_status,
)


class PaymentError(ValueError):
    """The payment can't be recorded on this invoice."""


def net_paid_on(invoice_id):
    """What's been paid on one invoice: successful payments minus refunds,
    ignoring voided rows. A SQL expression, so it works both for a single
    invoice id and correlated against Invoice.invoiceId in a larger query."""

    def total(event_type):
        return (
            select(func.coalesce(func.sum(BillingHistory.amount), 0))
            .where(
                BillingHistory.invoiceId == invoice_id,
                BillingHistory.eventType == event_type,
                BillingHistory.voidedAt.is_(None),
            )
            .scalar_subquery()
        )

    return total("Payment_Succeeded") - total("Refund_Issued")


def _remaining_balance(invoice: Invoice, db: Session):
    return invoice.invoiceAmount - db.execute(select(net_paid_on(invoice.invoiceId))).scalar_one()


def lock_invoice(invoice: Invoice, db: Session) -> Invoice:
    """Locks the invoice row until the caller commits, so two payments (or a
    payment and a void, or two accepts) on the same invoice run one after the
    other and each sees the other's result. populate_existing re-reads the row, in case its
    status changed while this request was waiting for the lock. Pending
    changes are flushed first, or that re-read would throw them away."""
    db.flush()
    return db.execute(
        select(Invoice)
        .where(Invoice.invoiceId == invoice.invoiceId)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one()


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
    # lock the record
    info = db.execute(
        select(BillingInfo)
        .where(BillingInfo.subprojectId == subproject_id)
        .with_for_update()
    ).scalar_one()

    active_invoices, total_invoiced = db.execute(
        select(
            func.count(),
            func.coalesce(func.sum(Invoice.invoiceAmount), 0),
        ).where(
            Invoice.subprojectId == subproject_id,
            Invoice.invoiceDeletedAt.is_(None),
            Invoice.invoiceStatus.in_(COUNTED_INVOICE_STATUSES),
        )
    ).one()

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

    if active_invoices == 0:
        # none accepted yet, or all deleted: nothing is billed, which isn't
        # the same as the client having paid everything
        status = "no_active_invoices"
    elif balance_due <= 0:
        status = "paid_in_full"
    elif total_paid > 0:
        status = "partial_payment_received"
    else:
        status = "payment_pending"

    # earliest due date among invoices that still owe money (net of
    # refunds); the read side compares it with now to report overdue
    next_due_date = db.execute(
        select(func.min(Invoice.dueDate)).where(
            Invoice.subprojectId == subproject_id,
            Invoice.invoiceDeletedAt.is_(None),
            Invoice.dueDate.is_not(None),
            Invoice.invoiceStatus.in_(COUNTED_INVOICE_STATUSES),
            net_paid_on(Invoice.invoiceId) < Invoice.invoiceAmount,
        )
    ).scalar_one()

    info.totalInvoiced = total_invoiced
    info.totalPaid = total_paid
    info.totalRefunded = total_refunded
    info.balanceDue = balance_due
    info.status = status
    info.nextDueDate = next_due_date
    info.lastEventAt = datetime.now(timezone.utc)


def record_payment(
    invoice: Invoice, amount: int, occurred_at, billing_metadata, db: Session
) -> BillingHistory:
    """The one place a "payment made" billing_history row gets written —
    always source="Manual" and eventType="Payment_Succeeded", since this is
    the vendor manually recording an offline payment (cash, check, bank
    transfer), not a Stripe webhook. Updates billing_info in the same
    transaction so the summary is never momentarily out of sync with the
    log that produced it.

    Only accepted invoices take payments, never more than what's left to pay,
    and the payment that brings the balance to zero marks the invoice Paid.
    Both checks run after the invoice row is locked: two payments arriving
    together could otherwise each see the same balance and both get through.
    Raises PaymentError."""
    invoice = lock_invoice(invoice, db)
    if invoice.invoiceStatus not in COUNTED_INVOICE_STATUSES:
        raise PaymentError("The client must accept this invoice before payments can be recorded.")
    balance = _remaining_balance(invoice, db)
    if amount > balance:
        raise PaymentError(
            "This invoice is already paid in full."
            if balance <= 0
            else f"The payment is more than the remaining balance of ${balance:,.2f}."
        )

    entry = BillingHistory(
        invoiceId=invoice.invoiceId,
        eventType="Payment_Succeeded",
        amount=amount,
        occurredAt=occurred_at or datetime.now(timezone.utc),
        source="Manual",
        billingMetadata=billing_metadata,
    )
    db.add(entry)
    db.flush()  # so the sums below see this row

    if invoice.subprojectId is not None:
        _recompute_billing_info(invoice.subprojectId, db)
    if amount == balance:
        change_invoice_status(invoice, "Paid")

    db.commit()
    db.refresh(entry)
    return entry


def void_payment(
    payment: BillingHistory, invoice: Invoice, reason: str, db: Session, actor_id=None
) -> BillingHistory:
    """Marks a payment recorded by mistake as void. The row stays in the
    history; it just stops counting toward the billing totals. The route has
    already checked that the payment can be voided.

    If the invoice was Paid and the void leaves something owing, it goes
    back to Accepted. Locks the invoice like record_payment, so a void and a
    payment on the same invoice can't interleave."""
    invoice = lock_invoice(invoice, db)
    payment.voidedAt = datetime.now(timezone.utc)
    payment.voidedReason = reason
    db.flush()  # so the sums below leave this payment out

    if invoice.subprojectId is not None:
        _recompute_billing_info(invoice.subprojectId, db)
    if invoice.invoiceStatus == "Paid" and _remaining_balance(invoice, db) > 0:
        change_invoice_status(invoice, "Accepted")

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
