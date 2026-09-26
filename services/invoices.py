from models import Invoice, Project, User
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload
from schemas.invoice import InvoiceUpdate
from services.invoice_pdf import generate_invoice_pdf
from services.notifications import create_notification

# InvoiceOut nests project -> client/vendor, same reasoning as
# services/subproject.py's _WITH_PROJECT_AND_USERS.
_WITH_PROJECT_AND_USERS = joinedload(Invoice.project).options(
    joinedload(Project.client),
    joinedload(Project.vendor),
)


def get_all_invoices(db: Session):
    return db.execute(select(Invoice).options(_WITH_PROJECT_AND_USERS)).scalars().all()

def get_invoice_by_id(invoice_id, db: Session):
    return db.get(Invoice, invoice_id, options=[_WITH_PROJECT_AND_USERS])

def get_invoices_by_user_id(user_id, db: Session):
    """For a non-vendor's GET /invoices — scoped by invoiceAssignedTo (who
    it's billed to), not by project, since one person can be billed across
    several of their own projects."""
    return db.execute(
        select(Invoice).where(Invoice.invoiceAssignedTo == user_id).options(_WITH_PROJECT_AND_USERS)
    ).scalars().all()

def get_invoices_by_project_id(project_id, db: Session):
    return db.execute(
        select(Invoice).where(Invoice.projectAssociatedTo == project_id).options(_WITH_PROJECT_AND_USERS)
    ).scalars().all()

def _regenerate_pdf(invoice: Invoice, db: Session) -> None:
    """The stored PDF always reflects the invoice's current data — called
    after every create AND every update, not just once at creation."""
    assigned_user = db.get(User, invoice.invoiceAssignedTo)
    generate_invoice_pdf(invoice, assigned_user)

def add_new_invoice(new_invoice, db: Session):
    created_invoice = Invoice(
        invoiceStatus=new_invoice.invoiceStatus,
        invoiceAmount=new_invoice.invoiceAmount,
        invoiceAssignedTo=new_invoice.invoiceAssignedTo,
        projectAssociatedTo=new_invoice.projectAssociatedTo,
    )
    db.add(created_invoice)
    db.commit()
    db.refresh(created_invoice)
    _regenerate_pdf(created_invoice, db)
    create_notification(
        db,
        user_id=created_invoice.invoiceAssignedTo,
        type="invoice_generated",
        message=f"A new invoice for ${created_invoice.invoiceAmount:,.2f} has been generated",
        related_invoice_id=created_invoice.invoiceId,
    )
    return created_invoice

def update_invoice_by_invoice_id(invoice_id, updates: InvoiceUpdate, db: Session):
    invoice = db.get(Invoice, invoice_id)
    if invoice is None:
        return None

    for field, value in updates.model_dump(exclude_unset=True).items():
        setattr(invoice, field, value)

    db.commit()
    db.refresh(invoice)
    _regenerate_pdf(invoice, db)
    return invoice

def respond_to_invoice(invoice: Invoice, new_status: str, db: Session) -> Invoice:
    """The client (or vendor, on their behalf) accepting/declining an
    invoice. Notifies BOTH the client (invoiceAssignedTo) and the
    project's vendor — regardless of which of the two performed the
    action, per the basic design: "each gets a notification.\""""
    invoice.invoiceStatus = new_status
    db.commit()
    db.refresh(invoice)
    _regenerate_pdf(invoice, db)

    status_word = new_status.lower()
    create_notification(
        db,
        user_id=invoice.invoiceAssignedTo,
        type=f"invoice_{status_word}",
        message=f"Your invoice was {status_word}",
        related_invoice_id=invoice.invoiceId,
    )
    if invoice.project.vendorOnProject is not None:
        create_notification(
            db,
            user_id=invoice.project.vendorOnProject,
            type=f"invoice_{status_word}",
            message=f"An invoice for \"{invoice.project.projectName}\" was {status_word} by the client",
            related_invoice_id=invoice.invoiceId,
        )
    return invoice

def delete_invoice_by_invoice_id(invoice_id, db: Session):
    invoice = db.get(Invoice, invoice_id)
    if invoice is None:
        return None

    db.delete(invoice)
    db.commit()
    return invoice
