from decimal import Decimal, ROUND_HALF_UP

from models import Invoice, Project, User
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload
from schemas.invoice import InvoiceUpdate
from services.invoice_pdf import generate_invoice_pdf
from services.notifications import create_notification
from services.account_activity import record_activity

# InvoiceOut nests project -> client/vendor, same reasoning as
# services/subproject.py's _WITH_PROJECT_AND_USERS.
_WITH_PROJECT_AND_USERS = joinedload(Invoice.project).options(
    selectinload(Project.users),
    joinedload(Project.vendor),
)


def get_all_invoices(organization_id, db: Session):
    """ "All invoices" now means all invoices in the caller's own
    organization — scoped by joining through Invoice's own project,
    since Invoice doesn't carry its own organizationId (Project is the
    single source of truth for which org a piece of business data belongs
    to)."""
    return (
        db.execute(
            select(Invoice)
            .join(Project, Invoice.projectAssociatedTo == Project.projectId)
            .where(Project.organizationId == organization_id)
            .options(_WITH_PROJECT_AND_USERS)
        )
        .scalars()
        .all()
    )


def get_invoice_by_id(invoice_id, db: Session):
    return db.get(Invoice, invoice_id, options=[_WITH_PROJECT_AND_USERS])


def get_invoices_by_user_id(user_id, db: Session):
    """For a non-vendor's GET /invoices — scoped by invoiceAssignedTo (who
    it's billed to), not by project, since one person can be billed across
    several of their own projects."""
    return (
        db.execute(
            select(Invoice)
            .where(Invoice.invoiceAssignedTo == user_id)
            .options(_WITH_PROJECT_AND_USERS)
        )
        .scalars()
        .all()
    )


def get_invoices_by_project_id(project_id, db: Session):
    return (
        db.execute(
            select(Invoice)
            .where(Invoice.projectAssociatedTo == project_id)
            .options(_WITH_PROJECT_AND_USERS)
        )
        .scalars()
        .all()
    )


def compute_invoice_amount(total_amount, deposit_percentage) -> Decimal:
    """totalAmount * depositPercentage / 100, rounded to the cent. Decimal so
    e.g. 33.33% of 1000 is 333.30, not 333.29999..."""
    amount = Decimal(str(total_amount)) * Decimal(str(deposit_percentage)) / 100
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def _regenerate_pdf(invoice: Invoice, db: Session) -> None:
    """The stored PDF always reflects the invoice's current data — called
    after every create AND every update, not just once at creation."""
    assigned_user = db.get(User, invoice.invoiceAssignedTo)
    generate_invoice_pdf(invoice, assigned_user)


def add_new_invoice(new_invoice, db: Session, actor_id=None):
    created_invoice = Invoice(
        invoiceStatus=new_invoice.invoiceStatus,
        invoiceAmount=compute_invoice_amount(new_invoice.totalAmount, new_invoice.depositPercentage),
        totalAmount=new_invoice.totalAmount,
        depositPercentage=new_invoice.depositPercentage,
        invoiceAssignedTo=new_invoice.invoiceAssignedTo,
        projectAssociatedTo=new_invoice.projectAssociatedTo,
        subprojectId=new_invoice.subprojectId,
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
    record_activity(
        db,
        activity_type="invoice_generated",
        description=f"An invoice for ${created_invoice.invoiceAmount:,.2f} was generated",
        project_id=created_invoice.projectAssociatedTo,
        actor_id=actor_id,
    )
    return created_invoice


def update_invoice_by_invoice_id(invoice_id, updates: InvoiceUpdate, db: Session):
    invoice = db.get(Invoice, invoice_id)
    if invoice is None:
        return None

    changes = updates.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(invoice, field, value)

    if "totalAmount" in changes or "depositPercentage" in changes:
        if invoice.totalAmount is None or invoice.depositPercentage is None:
            # only possible for invoices created before deposits existed
            db.rollback()
            raise ValueError("totalAmount and depositPercentage are both needed to compute invoiceAmount")
        invoice.invoiceAmount = compute_invoice_amount(invoice.totalAmount, invoice.depositPercentage)

    db.commit()
    db.refresh(invoice)
    _regenerate_pdf(invoice, db)
    return invoice


def respond_to_invoice(
    invoice: Invoice, new_status: str, db: Session, actor_id=None
) -> Invoice:
    """The client (or vendor, on their behalf) accepting/declining an
    invoice. Notifies BOTH the client (invoiceAssignedTo) and the
    project's vendor — regardless of which of the two performed the
    action, per the basic design: "each gets a notification.\" """
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
            message=f'An invoice for "{invoice.project.projectName}" was {status_word} by the client',
            related_invoice_id=invoice.invoiceId,
        )
    if new_status == "Accepted":
        record_activity(
            db,
            activity_type="invoice_accepted",
            description=f'Invoice for "{invoice.project.projectName}" was accepted by the client',
            project_id=invoice.projectAssociatedTo,
            actor_id=actor_id,
        )
    return invoice


def delete_invoice_by_invoice_id(invoice_id, db: Session):
    invoice = db.get(Invoice, invoice_id)
    if invoice is None:
        return None

    db.delete(invoice)
    db.commit()
    return invoice
