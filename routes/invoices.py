from sqlalchemy.orm import Session
from services.invoices import *
from fastapi import APIRouter, Depends, HTTPException
from models import Invoice
from schemas.invoice import InvoiceOut, InvoiceCreate, InvoiceUpdate
from database import get_db
from uuid import UUID

router = APIRouter()

@router.get("/invoices",response_model=list[InvoiceOut])
def get_invoices(db: Session= Depends(get_db)):
    invoices = get_all_invoices(db)
    return invoices

@router.get("/invoices/{invoice_id}", response_model=InvoiceOut)
def getinvoiceById(invoice_id:UUID, db:Session= Depends(get_db)):
     invoice = get_invoice_by_id(invoice_id, db)
     if invoice is None:
         raise HTTPException(status_code=404, detail="invoice not found")
     return invoice

@router.post("/invoices", response_model=InvoiceOut)
def add_invoice(new_invoice: InvoiceCreate, db:Session= Depends(get_db)):
     created_invoice = add_new_invoice(new_invoice, db)
     if created_invoice is None:
         raise HTTPException(status_code=409, detail=f"failure creating a new invoice")
     return created_invoice

@router.patch("/invoices/{invoice_id}", response_model=InvoiceOut)
def update_invoice(invoice_id: UUID, updates: InvoiceUpdate, db: Session = Depends(get_db)):
    updated_invoice = update_invoice_by_invoice_id(invoice_id, updates, db)
    if updated_invoice is None:
        raise HTTPException(status_code=404, detail="invoice not found")
    return updated_invoice

@router.delete("/invoices/{invoice_id}", status_code=204)
def delete_invoice(invoice_id: UUID, db: Session = Depends(get_db)):
    deleted_invoice = delete_invoice_by_invoice_id(invoice_id, db)
    if deleted_invoice is None:
        raise HTTPException(status_code=404, detail="invoice not found")

