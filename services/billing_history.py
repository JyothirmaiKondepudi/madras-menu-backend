from datetime import datetime, timezone

from models import BillingHistory, BillingInfo, Invoice, Subproject
from sqlalchemy import func, select
from sqlalchemy.orm import Session


def get_billing_history_by_id(billing_history_id, db: Session):
    return db.get(BillingHistory, billing_history_id)

def get_billing_history_by_invoice_id(invoice_id, db: Session):
    return db.execute(
        select(BillingHistory)
        .where(BillingHistory.invoiceId == invoice_id)
        .order_by(BillingHistory.occurredAt.desc())
    ).scalars().all()

def get_billing_history_by_subproject_id(subproject_id, db: Session):
    return db.execute(
        select(BillingHistory)
        .join(Invoice, BillingHistory.invoiceId == Invoice.invoiceId)
        .where(Invoice.subprojectId == subproject_id)
        .order_by(BillingHistory.occurredAt.desc())
    ).scalars().all()

def get_all_billing_history(db: Session):
    return db.execute(
        select(BillingHistory).order_by(BillingHistory.occurredAt.desc())
    ).scalars().all()

def get_billing_history_by_project_ids(project_ids, db: Session):
    """For a non-vendor's GET /billing-history — every transaction billed
    against a subproject belonging to any project they're linked to, the
    same scoping rule services/subproject.py's get_subprojects_by_project_ids
    already uses."""
    return db.execute(
        select(BillingHistory)
        .join(Invoice, BillingHistory.invoiceId == Invoice.invoiceId)
        .join(Subproject, Invoice.subprojectId == Subproject.subprojectId)
        .where(Subproject.projectAssociatedTo.in_(project_ids))
        .order_by(BillingHistory.occurredAt.desc())
    ).scalars().all()

def _recompute_billing_info(subproject_id, db: Session) -> None:
    """billing_info is a derived summary of billing_history, not
    independently maintained state — recomputed from the actual rows every
    time, rather than incrementally adjusted, so it can never drift out of
    sync with the log it's summarizing.

    billing_history.amount is cents (Integer); Invoice.invoiceAmount is
    dollars (Float) — an existing unit mismatch in this schema, not
    introduced here. Converting cents -> dollars at this one boundary
    keeps billing_info in the same dollar-float units Invoice already uses,
    rather than spreading the conversion across every caller.
    """
    total_invoiced = db.execute(
        select(func.coalesce(func.sum(Invoice.invoiceAmount), 0.0))
        .where(Invoice.subprojectId == subproject_id)
    ).scalar_one()

    total_paid_cents = db.execute(
        select(func.coalesce(func.sum(BillingHistory.amount), 0))
        .join(Invoice, BillingHistory.invoiceId == Invoice.invoiceId)
        .where(Invoice.subprojectId == subproject_id, BillingHistory.eventType == 'Payment_Succeeded')
    ).scalar_one()
    total_refunded_cents = db.execute(
        select(func.coalesce(func.sum(BillingHistory.amount), 0))
        .join(Invoice, BillingHistory.invoiceId == Invoice.invoiceId)
        .where(Invoice.subprojectId == subproject_id, BillingHistory.eventType == 'Refund_Issued')
    ).scalar_one()

    total_paid = total_paid_cents / 100
    total_refunded = total_refunded_cents / 100
    balance_due = total_invoiced - total_paid + total_refunded

    if balance_due <= 0:
        status = 'paid_in_full'
    elif total_paid > 0:
        status = 'partial_payment_received'
    else:
        status = 'payment_pending'

    info = db.get(BillingInfo, subproject_id)
    if info is None:
        info = BillingInfo(subprojectId=subproject_id)
        db.add(info)

    info.totalInvoiced = total_invoiced
    info.totalPaid = total_paid
    info.totalRefunded = total_refunded
    info.balanceDue = balance_due
    info.status = status
    info.lastEventAt = datetime.now(timezone.utc)

def record_payment(invoice: Invoice, amount: int, occurred_at, billing_metadata, db: Session) -> BillingHistory:
    """The one place a "payment made" billing_history row gets written —
    always source="Manual" and eventType="Payment_Succeeded", since this is
    the vendor manually recording an offline payment (cash, check, bank
    transfer), not a Stripe webhook. Updates billing_info in the same
    transaction so the summary is never momentarily out of sync with the
    log that produced it."""
    entry = BillingHistory(
        invoiceId=invoice.invoiceId,
        eventType='Payment_Succeeded',
        amount=amount,
        occurredAt=occurred_at or datetime.now(timezone.utc),
        source='Manual',
        billingMetadata=billing_metadata,
    )
    db.add(entry)

    if invoice.subprojectId is not None:
        db.flush()  # so the SUM query below sees this row
        _recompute_billing_info(invoice.subprojectId, db)

    db.commit()
    db.refresh(entry)
    return entry
