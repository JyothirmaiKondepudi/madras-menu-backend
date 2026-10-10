from sqlalchemy.orm import Session
from fastapi.responses import FileResponse
from services.invoices import *
from services.invoice_pdf import invoice_pdf_path
from services.billing_history import EDITABLE_INVOICE_STATUSES, count_live_payments
from fastapi import APIRouter, Depends, HTTPException
from models import Invoice, User, Project, Subproject
from schemas.invoice import InvoiceOut, InvoiceCreate, InvoiceUpdate
from database import get_db
from auth.dependencies import (
    get_current_user,
    require_permission,
    user_has_permission,
    user_project_ids,
    load_invoice_in_org,
    load_project_in_org,
    load_user_in_org,
)
from uuid import UUID

router = APIRouter()


@router.get("/invoices", response_model=list[InvoiceOut])
def get_invoices(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    if user_has_permission(current_user, "invoice:view_all", db):
        return get_all_invoices(current_user.userOrg, db)
    return get_invoices_by_user_id(current_user.userId, db)


@router.get("/invoices/projects/{project_id}", response_model=list[InvoiceOut])
def getInvoicesByProjectId(
    project_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    project: Project = Depends(load_project_in_org),
):
    if not user_has_permission(
        current_user, "invoice:view_all", db
    ) and project_id not in user_project_ids(current_user):
        raise HTTPException(
            status_code=403, detail="not authorized to view this project's invoices"
        )
    return get_invoices_by_project_id(project_id, db)


@router.get("/invoices/{invoice_id}", response_model=InvoiceOut)
def getinvoiceById(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    invoice: Invoice = Depends(load_invoice_in_org),
):
    if invoice is None:
        raise HTTPException(status_code=404, detail="invoice not found")
    if (
        not user_has_permission(current_user, "invoice:view_all", db)
        and invoice.invoiceAssignedTo != current_user.userId
    ):
        raise HTTPException(
            status_code=403, detail="not authorized to view this invoice"
        )
    return invoice


@router.post(
    "/invoices",
    response_model=InvoiceOut,
    dependencies=[Depends(require_permission("invoice:create"))],
)
def add_invoice(
    new_invoice: InvoiceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if new_invoice.invoiceAssignedTo is not None:
        load_user_in_org(new_invoice.invoiceAssignedTo, current_user, db)
        project = db.get(Project, new_invoice.projectAssociatedTo)
    if project is None or project.organizationId != current_user.userOrg:
        raise HTTPException(status_code=404, detail="project not found")

    if new_invoice.subprojectId is not None:
        subproject = db.get(Subproject, new_invoice.subprojectId)
        if subproject is None or subproject.projectAssociatedTo != project.projectId:
            raise HTTPException(status_code=404, detail="subproject not found")
    created_invoice = add_new_invoice(new_invoice, db, actor_id=current_user.userId)
    if created_invoice is None:
        raise HTTPException(status_code=409, detail=f"failure creating a new invoice")
    return created_invoice


@router.patch(
    "/invoices/{invoice_id}",
    response_model=InvoiceOut,
    dependencies=[Depends(require_permission("invoice:update"))],
)
def update_invoice(
    invoice_id: UUID,
    updates: InvoiceUpdate,
    db: Session = Depends(get_db),
    invoice: Invoice = Depends(load_invoice_in_org),
    current_user: User = Depends(get_current_user),
):
    if updates.invoiceAssignedTo is not None:
        load_user_in_org(updates.invoiceAssignedTo, current_user, db)

    if updates.subprojectId is not None:
        subproject = db.get(Subproject, updates.subprojectId)
        if (
            subproject is None
            or subproject.projectAssociatedTo != invoice.projectAssociatedTo
        ):
            raise HTTPException(status_code=404, detail="subproject not found")

    # same rule as delete: once the client has accepted or paid, the invoice
    # stays on its event. model_fields_set so an explicit null counts as a move
    if (
        "subprojectId" in updates.model_fields_set
        and updates.subprojectId != invoice.subprojectId
    ):
        if invoice.invoiceStatus not in EDITABLE_INVOICE_STATUSES:
            raise HTTPException(
                status_code=409,
                detail=f"{invoice.invoiceStatus} invoices can't be moved to another subproject.",
            )
        payment_count = count_live_payments(invoice_id, db)
        if payment_count:
            raise HTTPException(
                status_code=409,
                detail=f"This invoice has {payment_count} payments. Void them before moving the invoice.",
            )
    load_invoice_in_org(invoice_id, current_user, db)
    try:
        updated_invoice = update_invoice_by_invoice_id(invoice_id, updates, db)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if updated_invoice is None:
        raise HTTPException(status_code=404, detail="invoice not found")
    return updated_invoice


@router.delete(
    "/invoices/{invoice_id}",
    status_code=204,
    dependencies=[Depends(require_permission("invoice:delete"))],
)
def delete_invoice(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    invoice: Invoice = Depends(load_invoice_in_org),
    current_user: User = Depends(get_current_user),
):
    # only invoices the client hasn't accepted yet can be deleted
    if invoice.invoiceStatus not in EDITABLE_INVOICE_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=f"{invoice.invoiceStatus} invoices can't be deleted.",
        )
    payment_count = count_live_payments(invoice_id, db)
    if payment_count:
        raise HTTPException(
            status_code=409,
            detail=f"This invoice has {payment_count} payments. Void them before deleting the invoice.",
        )
    deleted_invoice = delete_invoice_by_invoice_id(
        invoice_id, db, actor_id=current_user.userId
    )
    if deleted_invoice is None:
        raise HTTPException(status_code=404, detail="invoice not found")


@router.patch("/invoices/{invoice_id}/accept", response_model=InvoiceOut)
def accept_invoice(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    invoice: Invoice = Depends(load_invoice_in_org),
):
    invoice = get_invoice_by_id(invoice_id, db)
    if invoice is None:
        raise HTTPException(status_code=404, detail="invoice not found")
    if (
        not user_has_permission(current_user, "invoice:view_all", db)
        and invoice.invoiceAssignedTo != current_user.userId
    ):
        raise HTTPException(
            status_code=403, detail="not authorized to respond to this invoice"
        )
    return respond_to_invoice(invoice, "Accepted", db, actor_id=current_user.userId)


@router.patch("/invoices/{invoice_id}/reject", response_model=InvoiceOut)
def reject_invoice(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    invoice: Invoice = Depends(load_invoice_in_org),
):
    invoice = get_invoice_by_id(invoice_id, db)
    if invoice is None:
        raise HTTPException(status_code=404, detail="invoice not found")
    if (
        not user_has_permission(current_user, "invoice:view_all", db)
        and invoice.invoiceAssignedTo != current_user.userId
    ):
        raise HTTPException(
            status_code=403, detail="not authorized to respond to this invoice"
        )
    if invoice.invoiceStatus not in EDITABLE_INVOICE_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=f"{invoice.invoiceStatus} invoices can't be rejected.",
        )
    return respond_to_invoice(invoice, "Declined", db, actor_id=current_user.userId)


@router.get("/invoices/{invoice_id}/pdf")
def get_invoice_pdf(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    invoice: Invoice = Depends(load_invoice_in_org),
):
    invoice = get_invoice_by_id(invoice_id, db)
    if invoice is None:
        raise HTTPException(status_code=404, detail="invoice not found")
    if (
        not user_has_permission(current_user, "invoice:view_all", db)
        and invoice.invoiceAssignedTo != current_user.userId
    ):
        raise HTTPException(
            status_code=403, detail="not authorized to view this invoice"
        )

    path = invoice_pdf_path(invoice_id)
    if not path.exists():
        # Shouldn't happen for any invoice created after this feature
        # shipped — add_new_invoice always generates one — but an invoice
        # created before it existed would have no file on disk.
        raise HTTPException(
            status_code=404, detail="no PDF has been generated for this invoice"
        )
    return FileResponse(
        path, media_type="application/pdf", filename=f"invoice-{invoice_id}.pdf"
    )
