from sqlalchemy.orm import Session
from fastapi.responses import FileResponse
from services.invoices import (
    invoices_for_user_query,
    invoices_in_org_query,
    invoices_in_project_query,
    add_new_invoice,
    delete_invoice_by_invoice_id,
    regenerate_pdf,
    respond_to_invoice,
    update_invoice_by_invoice_id,
)
from services.invoice_status import COUNTED_INVOICE_STATUSES, InvoiceStatusError
from services.invoice_document import InvoiceDocumentError
from services.invoice_pdf import invoice_pdf_path
from services.billing_history import (
    EDITABLE_INVOICE_STATUSES,
    count_live_payments,
    net_paid_on,
)
from services.listing import Listing, Page, paginate
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from models import Invoice, User, Project, Subproject
from schemas.invoice import InvoiceOut, InvoiceCreate, InvoiceUpdate
from database import get_db
from auth.dependencies import (
    ensure_own_or_permission,
    ensure_project_access,
    get_current_user,
    load_invoice_in_org,
    load_project_in_org,
    load_user_in_org,
    require_permission,
    user_has_permission,
)
import logging
from uuid import UUID

router = APIRouter()
logger = logging.getLogger("uvicorn.error")


INVOICE_SORTS = {
    "createdAt": Invoice.createdAt,
    "dueDate": Invoice.dueDate,
    "invoiceAmount": Invoice.invoiceAmount,
    "totalAmount": Invoice.totalAmount,
    "invoiceStatus": Invoice.invoiceStatus,
}
InvoiceStatus = InvoiceOut.model_fields["invoiceStatus"].annotation


def _list_invoices(db, stmt, listing, status, due_from, due_to, overdue):
    if status is not None:
        stmt = stmt.where(Invoice.invoiceStatus == status)
    if due_from is not None:
        stmt = stmt.where(Invoice.dueDate >= due_from)
    if due_to is not None:
        stmt = stmt.where(Invoice.dueDate <= due_to)
    if overdue:
        # the same rule billing info uses: accepted, past due, still owing
        stmt = stmt.where(
            Invoice.dueDate < datetime.now(timezone.utc),
            Invoice.invoiceStatus.in_(COUNTED_INVOICE_STATUSES),
            net_paid_on(Invoice.invoiceId) < Invoice.invoiceAmount,
        )
    return paginate(db, stmt, listing, INVOICE_SORTS, "-createdAt", Invoice.invoiceId)


@router.get("/invoices", response_model=Page[InvoiceOut])
def get_invoices(
    listing: Listing,
    status: InvoiceStatus | None = None,
    due_from: datetime | None = Query(None, alias="dueFrom"),
    due_to: datetime | None = Query(None, alias="dueTo"),
    overdue: bool = Query(False, description="only invoices past due and still owing"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if user_has_permission(current_user, "invoice:view_all", db):
        stmt = invoices_in_org_query(current_user.userOrg)
    else:
        stmt = invoices_for_user_query(current_user.userId)
    return _list_invoices(db, stmt, listing, status, due_from, due_to, overdue)


@router.get("/projects/{project_id}/invoices", response_model=Page[InvoiceOut])
def getInvoicesByProjectId(
    project_id: UUID,
    listing: Listing,
    status: InvoiceStatus | None = None,
    due_from: datetime | None = Query(None, alias="dueFrom"),
    due_to: datetime | None = Query(None, alias="dueTo"),
    overdue: bool = Query(False, description="only invoices past due and still owing"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    project: Project = Depends(load_project_in_org),
):
    ensure_project_access(
        current_user,
        project_id,
        "invoice:view_all",
        db,
        "not authorized to view this project's invoices",
    )
    stmt = invoices_in_project_query(project_id)
    return _list_invoices(db, stmt, listing, status, due_from, due_to, overdue)


@router.get("/invoices/{invoice_id}", response_model=InvoiceOut)
def getinvoiceById(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    invoice: Invoice = Depends(load_invoice_in_org),
):
    if invoice is None:
        raise HTTPException(status_code=404, detail="invoice not found")
    ensure_own_or_permission(
        current_user,
        invoice.invoiceAssignedTo == current_user.userId,
        "invoice:view_all",
        db,
        "not authorized to view this invoice",
    )
    return invoice


def ensure_project_member(project: Project, user_id: UUID) -> None:
    """The billed client has to be linked to the invoice's project. The
    database enforces this too (invoices_assignee_project_member_fkey); this
    check runs first so the caller gets a clear 422 instead of a 500."""
    if not any(user.userId == user_id for user in project.users):
        raise HTTPException(
            status_code=422,
            detail="The invoice can only be assigned to a member of its project.",
        )


def _respond(invoice: Invoice, new_status: str, db: Session, current_user: User):
    """Accept or reject, allowed only from where the transitions table says."""
    try:
        invoice = respond_to_invoice(
            invoice, new_status, db, actor_id=current_user.userId
        )
    except InvoiceStatusError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc))
    db.commit()
    try:
        regenerate_pdf(invoice, db)
    except Exception:
        logger.exception(f"PDF generation failed for invoice ID: {invoice.invoiceId}")
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
    project = db.get(Project, new_invoice.projectAssociatedTo)
    if project is None or project.organizationId != current_user.userOrg:
        raise HTTPException(status_code=404, detail="project not found")
    load_user_in_org(new_invoice.invoiceAssignedTo, current_user, db)
    ensure_project_member(project, new_invoice.invoiceAssignedTo)

    if new_invoice.subprojectId is not None:
        subproject = db.get(Subproject, new_invoice.subprojectId)
        if subproject is None or subproject.projectAssociatedTo != project.projectId:
            raise HTTPException(status_code=404, detail="subproject not found")
    try:
        created_invoice = add_new_invoice(new_invoice, db, actor_id=current_user.userId)
    except InvoiceDocumentError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if created_invoice is None:
        raise HTTPException(status_code=409, detail=f"failure creating a new invoice")
    db.commit()
    try:
        regenerate_pdf(created_invoice, db)
    except Exception:
        logger.exception(
            f"PDF generation failed for invoice ID: {created_invoice.invoiceId}"
        )
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
        ensure_project_member(invoice.project, updates.invoiceAssignedTo)

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
    # the document (lines, adjustment, currency) is what the client agrees
    # to, so like moving it, it only changes before they accept
    document_fields = {"lineItems", "adjustmentPercentage", "currency"}
    if document_fields & updates.model_fields_set and invoice.invoiceStatus not in EDITABLE_INVOICE_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=f"{invoice.invoiceStatus} invoices' line items, adjustment and currency can't be changed.",
        )
    load_invoice_in_org(invoice_id, current_user, db)
    try:
        updated_invoice = update_invoice_by_invoice_id(invoice_id, updates, db)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if updated_invoice is None:
        raise HTTPException(status_code=404, detail="invoice not found")
    db.commit()
    try:
        regenerate_pdf(updated_invoice, db)
    except Exception:
        logger.exception(f"PDF generation failed for invoice ID: {invoice.invoiceId}")
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
    db.commit()


@router.post("/invoices/{invoice_id}/accept", response_model=InvoiceOut)
def accept_invoice(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    invoice: Invoice = Depends(load_invoice_in_org),
):

    if invoice is None:
        raise HTTPException(status_code=404, detail="invoice not found")
    ensure_own_or_permission(
        current_user,
        invoice.invoiceAssignedTo == current_user.userId,
        "invoice:view_all",
        db,
        "not authorized to respond to this invoice",
    )

    return _respond(invoice, "Accepted", db, current_user)


@router.post("/invoices/{invoice_id}/reject", response_model=InvoiceOut)
def reject_invoice(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    invoice: Invoice = Depends(load_invoice_in_org),
):
    if invoice is None:
        raise HTTPException(status_code=404, detail="invoice not found")
    ensure_own_or_permission(
        current_user,
        invoice.invoiceAssignedTo == current_user.userId,
        "invoice:view_all",
        db,
        "not authorized to respond to this invoice",
    )
    return _respond(invoice, "Declined", db, current_user)


@router.get("/invoices/{invoice_id}/pdf")
def get_invoice_pdf(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    invoice: Invoice = Depends(load_invoice_in_org),
):
    ensure_own_or_permission(
        current_user,
        invoice.invoiceAssignedTo == current_user.userId,
        "invoice:view_all",
        db,
        "not authorized to view this invoice",
    )

    path = invoice_pdf_path(invoice_id)
    if not path.exists():
        # Shouldn't happen for any invoice created after this feature
        # shipped — add_new_invoice always generates one — but an invoice
        # created before it existed would have no file on disk.
        try:
            regenerate_pdf(invoice, db)
        except Exception:
            logger.exception(
                f"PDF generation failed for invoice ID:{invoice.invoiceId}"
            )
            raise HTTPException(
                status_code=503,
                detail="The invoice PDF couldn't be generated. Please try again.",
            )
    return FileResponse(
        path, media_type="application/pdf", filename=f"invoice-{invoice_id}.pdf"
    )
