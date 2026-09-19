"""
Generates and stores a PDF for an invoice. Kept separate from
services/invoices.py (a plain DB-CRUD file) since this is a genuinely
different kind of concern — building a binary document, not querying the
database — same reasoning that split embeddings/hierarchy into their own
modules rather than dumping everything into one file.

Storage: generate-and-store, not generate-on-demand. The PDF is built and
saved to disk on every create AND every update (services/invoices.py calls
this after both), so re-fetching it later (GET /invoices/{id}/pdf) always
serves the current state — never a stale snapshot from creation time.
"""

import os
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from models import Invoice, User

# Default lives next to the repo, not tied to whatever directory the
# process happens to be started from.
INVOICE_PDF_DIR = Path(
    os.environ.get("INVOICE_PDF_DIR", Path(__file__).resolve().parent.parent / "storage" / "invoices")
)


def invoice_pdf_path(invoice_id) -> Path:
    return INVOICE_PDF_DIR / f"{invoice_id}.pdf"


def generate_invoice_pdf(invoice: Invoice, assigned_user: User) -> Path:
    INVOICE_PDF_DIR.mkdir(parents=True, exist_ok=True)
    path = invoice_pdf_path(invoice.invoiceId)

    c = canvas.Canvas(str(path), pagesize=letter)
    width, height = letter

    c.setFont("Helvetica-Bold", 18)
    c.drawString(72, height - 72, "Madras Catering — Invoice")

    c.setFont("Helvetica", 11)
    lines = [
        f"Invoice ID: {invoice.invoiceId}",
        f"Project: {invoice.project.projectName}",
        f"Status: {invoice.invoiceStatus}",
        f"Amount: ${invoice.invoiceAmount:,.2f}",
        "",
        f"Billed to: {assigned_user.fullName}",
        f"Email: {assigned_user.userEmail}",
    ]
    y = height - 120
    for line in lines:
        c.drawString(72, y, line)
        y -= 20

    c.save()
    return path
