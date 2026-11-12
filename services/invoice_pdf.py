"""Generates and stores a PDF for an invoice. Called by services/invoices.py on
every create and update, so the stored file always reflects current state."""

import os
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from models import Invoice, User

INVOICE_PDF_DIR = Path(
    os.environ.get("INVOICE_PDF_DIR", Path(__file__).resolve().parent.parent / "storage" / "invoices")
)


def invoice_pdf_path(invoice_id) -> Path:
    return INVOICE_PDF_DIR / f"{invoice_id}.pdf"


def _plain(value) -> str:
    """3.00 -> "3", 2.50 -> "2.5": quantities and percentages without
    trailing zeros (Decimal's :g keeps them)."""
    text = f"{value:f}"
    return text.rstrip("0").rstrip(".") if "." in text else text


def _money(value, currency: str) -> str:
    return f"{currency} {value:,.2f}" if currency != "USD" else f"${value:,.2f}"


def _invoice_lines(invoice: Invoice, assigned_user: User) -> list[tuple[str, str]]:
    """(style, text) lines for the page: the business header, who it's
    billed to, the line items and totals, then terms and deliverables."""
    business = invoice.businessSnapshot or {}
    client = invoice.clientSnapshot or {
        "fullName": assigned_user.fullName, "email": assigned_user.userEmail,
    }
    currency = invoice.currency or "USD"
    out = [("title", business.get("name") or "Invoice")]
    for key in ("address", "phone", "email"):
        if business.get(key):
            out.append(("small", business[key]))
    if business.get("ein"):
        out.append(("small", f"EIN {business['ein']}"))
    out += [("gap", ""), ("bold", f"Invoice {invoice.invoiceNumber or invoice.invoiceId}")]
    out += [
        ("text", f"Project: {invoice.project.projectName}"),
        ("text", f"Status: {invoice.invoiceStatus}"),
    ]
    if invoice.dueDate is not None:
        out.append(("text", f"Due: {invoice.dueDate:%Y-%m-%d}"))
    out += [("gap", ""), ("bold", "Billed to"), ("text", client.get("fullName") or "")]
    for key in ("email", "phone", "address"):
        if client.get(key):
            out.append(("text", client[key]))

    if invoice.lineItems:
        out += [("gap", ""), ("bold", "Items")]
        for item in invoice.lineItems:
            unit = f" / {item.pricingUnit}" if item.pricingUnit else ""
            out.append((
                "text",
                f"{item.name}: {_plain(item.quantity)} x {_money(item.unitPrice, currency)}{unit}"
                f" = {_money(item.lineTotal, currency)}",
            ))
        out += [("gap", ""), ("text", f"Subtotal: {_money(invoice.subtotalAmount, currency)}")]
        if invoice.adjustmentPercentage:
            label = "Discount" if invoice.adjustmentPercentage < 0 else "Surcharge"
            out.append(("text", f"{label}: {_plain(abs(invoice.adjustmentPercentage))}%"))
    if invoice.totalAmount is not None:
        out.append(("text", f"Event total: {_money(invoice.totalAmount, currency)}"))
    if invoice.depositPercentage is not None:
        out.append(("text", f"Deposit: {_plain(invoice.depositPercentage)}%"))
    out.append(("bold", f"Amount due: {_money(invoice.invoiceAmount, currency)}"))

    for heading, body in (("Deliverables", invoice.deliverables), ("Terms", invoice.legalTerms)):
        if body:
            out += [("gap", ""), ("bold", heading)]
            out += [("small", line) for line in body.splitlines() or [""]]
    return out


def generate_invoice_pdf(invoice: Invoice, assigned_user: User) -> Path:
    INVOICE_PDF_DIR.mkdir(parents=True, exist_ok=True)
    path = invoice_pdf_path(invoice.invoiceId)

    c = canvas.Canvas(str(path), pagesize=letter)
    width, height = letter
    fonts = {"title": ("Helvetica-Bold", 18, 26), "bold": ("Helvetica-Bold", 11, 18),
             "text": ("Helvetica", 11, 16), "small": ("Helvetica", 9, 13), "gap": ("Helvetica", 9, 10)}
    y = height - 72
    for style, line in _invoice_lines(invoice, assigned_user):
        font, size, step = fonts[style]
        if y < 72:  # new page when this one is full
            c.showPage()
            y = height - 72
        c.setFont(font, size)
        c.drawString(72, y, line)
        y -= step

    c.save()
    return path
