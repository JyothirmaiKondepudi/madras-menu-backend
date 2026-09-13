from model import Invoice
from sqlalchemy.orm import Session
from schemas.invoice import InvoiceUpdate


def get_all_invoices(db: Session):
    return db.query(Invoice).all()

def get_invoice_by_id(invoice_id, db: Session):
    return db.query(Invoice).get(invoice_id)

def add_new_invoice(new_invoice, db: Session):
    created_invoice = Invoice(
        invoiceStatus=new_invoice.invoiceStatus,
        invoiceAmount=new_invoice.invoiceAmount,
        invoiceAssignedTo=new_invoice.invoiceAssignedTo,
    )
    db.add(created_invoice)
    db.commit()
    db.refresh(created_invoice)
    return created_invoice

def update_invoice_by_invoice_id(invoice_id, updates: InvoiceUpdate, db: Session):
    invoice = db.query(Invoice).get(invoice_id)
    if invoice is None:
        return None

    for field, value in updates.model_dump(exclude_unset=True).items():
        setattr(invoice, field, value)

    db.commit()
    db.refresh(invoice)
    return invoice

def delete_invoice_by_invoice_id(invoice_id, db: Session):
    invoice = db.query(Invoice).get(invoice_id)
    if invoice is None:
        return None

    db.delete(invoice)
    db.commit()
    return invoice
