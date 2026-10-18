from sqlalchemy.orm import Session
from services.billing_history import (
    billing_history_for_invoice_query,
    billing_history_for_subproject_query,
    billing_history_in_org_query,
    billing_history_in_projects_query,
    PaymentError,
    record_payment,
    void_payment,
)
from services.invoices import get_live_invoice
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from services.listing import Listing, Page, paginate
from models import BillingHistory, User, Invoice, Subproject
from schemas.billing_history import BillingHistoryOut, PaymentCreate, VoidPaymentRequest
from database import get_db
from auth.dependencies import (
    ensure_own_or_permission,
    ensure_project_access,
    get_current_user,
    load_invoice_in_org,
    load_subproject_in_org,
    require_permission,
    user_has_permission,
    user_project_ids,
)
from uuid import UUID

router = APIRouter()


@router.post(
    "/billing-history/payments",
    response_model=BillingHistoryOut,
    dependencies=[Depends(require_permission("billing:create"))],
)
def record_payment_made(
    new_payment: PaymentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    invoice = get_live_invoice(db, new_payment.invoiceId)
    if invoice is None or invoice.project.organizationId != current_user.userOrg:
        raise HTTPException(status_code=404, detail="invoice not found")
    try:
        payment = record_payment(
            invoice,
            amount=new_payment.amount,
            occurred_at=new_payment.occurredAt,
            billing_metadata=new_payment.billingMetadata,
            db=db,
        )
    except PaymentError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc))
    db.commit()
    return payment


@router.post(
    "/billing-history/{payment_id}/void",
    response_model=BillingHistoryOut,
    dependencies=[Depends(require_permission("billing:void"))],
)
def void_payment_made(
    payment_id: UUID,
    body: VoidPaymentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payment = db.get(BillingHistory, payment_id)
    # a deleted invoice is filtered out, so its payments read as not found too
    invoice = get_live_invoice(db, payment.invoiceId) if payment is not None else None
    if invoice is None or invoice.project.organizationId != current_user.userOrg:
        raise HTTPException(status_code=404, detail="payment not found")
    if payment.voidedAt is not None:
        raise HTTPException(status_code=409, detail="This payment is already voided.")
    if payment.eventType != "Payment_Succeeded":
        raise HTTPException(
            status_code=409, detail="Only successful payments can be voided."
        )
    if payment.source != "Manual":
        # card payments really moved money; they're refunded, not voided
        raise HTTPException(
            status_code=409,
            detail=f"{payment.source} payments can't be voided. Issue a refund instead.",
        )
    voided_payment = void_payment(
        payment, invoice, body.reason, db, actor_id=current_user.userId
    )
    db.commit()
    return voided_payment


BILLING_HISTORY_SORTS = {
    "occurredAt": BillingHistory.occurredAt,
    "amount": BillingHistory.amount,
}
BillingEventType = BillingHistoryOut.model_fields["eventType"].annotation


def _list_billing_history(db, stmt, listing, event_type, occurred_from, occurred_to):
    if event_type is not None:
        stmt = stmt.where(BillingHistory.eventType == event_type)
    if occurred_from is not None:
        stmt = stmt.where(BillingHistory.occurredAt >= occurred_from)
    if occurred_to is not None:
        stmt = stmt.where(BillingHistory.occurredAt <= occurred_to)
    return paginate(
        db, stmt, listing, BILLING_HISTORY_SORTS, "-occurredAt", BillingHistory.id
    )


@router.get("/billing-history", response_model=Page[BillingHistoryOut])
def get_billing_history(
    listing: Listing,
    event_type: BillingEventType | None = Query(None, alias="eventType"),
    occurred_from: datetime | None = Query(None, alias="occurredFrom"),
    occurred_to: datetime | None = Query(None, alias="occurredTo"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if user_has_permission(current_user, "billing:view_all", db):
        stmt = billing_history_in_org_query(current_user.userOrg)
    else:
        stmt = billing_history_in_projects_query(user_project_ids(current_user))
    return _list_billing_history(db, stmt, listing, event_type, occurred_from, occurred_to)


@router.get(
    "/subprojects/{subproject_id}/billing-history",
    response_model=Page[BillingHistoryOut],
)
def get_billing_history_for_subproject(
    subproject_id: UUID,
    listing: Listing,
    event_type: BillingEventType | None = Query(None, alias="eventType"),
    occurred_from: datetime | None = Query(None, alias="occurredFrom"),
    occurred_to: datetime | None = Query(None, alias="occurredTo"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    subproject: Subproject = Depends(load_subproject_in_org),
):
    ensure_project_access(
        current_user,
        subproject.projectAssociatedTo,
        "billing:view_all",
        db,
        "not authorized to view this subproject's billing history",
    )
    stmt = billing_history_for_subproject_query(subproject_id)
    return _list_billing_history(db, stmt, listing, event_type, occurred_from, occurred_to)


@router.get(
    "/invoices/{invoice_id}/billing-history", response_model=Page[BillingHistoryOut]
)
def get_billing_history_for_invoice(
    invoice_id: UUID,
    listing: Listing,
    event_type: BillingEventType | None = Query(None, alias="eventType"),
    occurred_from: datetime | None = Query(None, alias="occurredFrom"),
    occurred_to: datetime | None = Query(None, alias="occurredTo"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    invoice: Invoice = Depends(load_invoice_in_org),
):
    if invoice is None:
        raise HTTPException(status_code=404, detail="invoice not found")
    ensure_own_or_permission(
        current_user,
        invoice.invoiceAssignedTo == current_user.userId,
        "billing:view_all",
        db,
        "not authorized to view this invoice's billing history",
    )
    stmt = billing_history_for_invoice_query(invoice_id)
    return _list_billing_history(db, stmt, listing, event_type, occurred_from, occurred_to)
