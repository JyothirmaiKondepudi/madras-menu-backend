from sqlalchemy.orm import Session
from services.billing_history import *
from services.subproject import get_subproject_by_subproject_id
from services.invoices import get_invoice_by_id
from fastapi import APIRouter, Depends, HTTPException
from models import User, Invoice
from schemas.billing_history import BillingHistoryOut, PaymentCreate
from database import get_db
from auth.dependencies import (
    get_current_user,
    user_project_ids,
    user_has_permission,
    require_permission,
    load_invoice_in_org,
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
    invoice = db.get(Invoice, new_payment.invoiceId)
    if invoice is None or invoice.project.organizationId != current_user.userOrg:
        raise HTTPException(status_code=404, detail="invoice not found")
    return record_payment(
        invoice,
        amount=new_payment.amount,
        occurred_at=new_payment.occurredAt,
        billing_metadata=new_payment.billingMetadata,
        db=db,
    )


@router.get("/billing-history", response_model=list[BillingHistoryOut])
def get_billing_history(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    if user_has_permission(current_user, "billing:view_all", db):
        return get_all_billing_history(db)
    return get_billing_history_by_project_ids(user_project_ids(current_user), db)


@router.get(
    "/billing-history/subprojects/{subproject_id}",
    response_model=list[BillingHistoryOut],
)
def get_billing_history_for_subproject(
    subproject_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    subproject = get_subproject_by_subproject_id(subproject_id, db)
    if subproject is None:
        raise HTTPException(status_code=404, detail="subproject not found")
    if not user_has_permission(
        current_user, "billing:view_all", db
    ) and subproject.projectAssociatedTo not in user_project_ids(current_user):
        raise HTTPException(
            status_code=403,
            detail="not authorized to view this subproject's billing history",
        )
    return get_billing_history_by_subproject_id(subproject_id, db)


@router.get(
    "/billing-history/invoices/{invoice_id}", response_model=list[BillingHistoryOut]
)
def get_billing_history_for_invoice(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    invoice: Invoice = Depends(load_invoice_in_org),
):
    if invoice is None:
        raise HTTPException(status_code=404, detail="invoice not found")
    if (
        not user_has_permission(current_user, "billing:view_all", db)
        and invoice.invoiceAssignedTo != current_user.userId
    ):
        raise HTTPException(
            status_code=403,
            detail="not authorized to view this invoice's billing history",
        )
    return get_billing_history_by_invoice_id(invoice_id, db)
