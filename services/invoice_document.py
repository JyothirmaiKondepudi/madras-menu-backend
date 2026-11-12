"""The invoice as a document (BE-04): its number, line items, totals and the
snapshot of business and client details printed on it.

Totals: each line is quantity x unit price, rounded to the cent; the subtotal
is their sum; the adjustment percentage (-10 = 10% discount, 5 = 5% surcharge)
turns the subtotal into totalAmount; the deposit percentage turns that into
invoiceAmount, as before.
"""

from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import text
from sqlalchemy.orm import Session

from models import Equipment, Invoice, InvoiceLineItem, Organization, RateCardItem, User

CENT = Decimal("0.01")


class InvoiceDocumentError(ValueError):
    """The invoice's line items or totals can't be accepted as given."""


def _cents(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def next_invoice_number(org_id, db: Session) -> str:
    """INV-<year>-<n>, counting from 1 each year per organization. A single
    upsert, so two invoices created at the same moment can't get the same
    number: the second waits for the first's row and gets the next one."""
    year = datetime.now(timezone.utc).year
    number = db.execute(
        text(
            "INSERT INTO invoice_number_counters (org_id, year, last_number) "
            "VALUES (:org, :year, 1) "
            "ON CONFLICT (org_id, year) DO UPDATE "
            "SET last_number = invoice_number_counters.last_number + 1 "
            "RETURNING last_number"
        ),
        {"org": org_id, "year": year},
    ).scalar_one()
    return f"INV-{year}-{number:04d}"


def build_line_items(lines, org_id, db: Session) -> list[InvoiceLineItem]:
    """Turns the request's lines into rows. A service or equipment line with
    a sourceId copies its name, price (and pricing unit) from the
    organization's catalog unless the line overrides them; a custom line
    must give both."""
    models = {"service": RateCardItem, "equipment": Equipment}
    built = []
    for position, line in enumerate(lines):
        name, unit_price, pricing_unit = line.name, line.unitPrice, None
        if line.sourceId is not None:
            source = db.get(models[line.kind], line.sourceId)
            if source is None or source.orgId != org_id:
                raise InvoiceDocumentError(
                    f"line {position + 1}: no {line.kind} {line.sourceId} in this organization's catalog"
                )
            name = name if name is not None else source.name
            if line.kind == "service":
                unit_price = unit_price if unit_price is not None else source.price
                pricing_unit = source.pricingUnit
            else:
                unit_price = unit_price if unit_price is not None else source.amount
        if name is None or unit_price is None:
            raise InvoiceDocumentError(
                f"line {position + 1}: a line without a catalog item needs a name and a unitPrice"
            )
        built.append(
            InvoiceLineItem(
                position=position,
                kind=line.kind,
                sourceId=line.sourceId,
                name=name,
                quantity=line.quantity,
                unitPrice=unit_price,
                pricingUnit=pricing_unit,
                lineTotal=_cents(line.quantity * unit_price),
            )
        )
    return built


def totals(line_items: list[InvoiceLineItem], adjustment_percentage) -> tuple[Decimal, Decimal]:
    """(subtotal, total) for the line items and adjustment."""
    subtotal = _cents(sum((item.lineTotal for item in line_items), Decimal("0")))
    adjustment = Decimal(str(adjustment_percentage or 0))
    total = _cents(subtotal * (Decimal("100") + adjustment) / Decimal("100"))
    if total <= 0:
        raise InvoiceDocumentError("the invoice total must be more than zero")
    return subtotal, total


def business_snapshot(org: Organization) -> dict:
    return {
        "name": org.orgName,
        "email": org.orgEmail,
        "phone": org.orgPhone,
        "address": org.orgAddress,
        "ein": org.orgEin,
        "country": org.orgCountry,
        "logoUrl": org.orgLogoUrl,
        "websites": list(org.orgWebsites or []),
        "socials": dict(org.orgSocials or {}),
    }


def client_snapshot(user: User) -> dict:
    return {
        "userId": str(user.userId),
        "fullName": user.fullName,
        "email": user.userEmail,
        "phone": user.userPhoneNumber,
        "address": user.userAddress,
    }


def refresh_snapshots(invoice: Invoice, db: Session) -> None:
    """Copies the business and client details onto the invoice. Called while
    the invoice is being written or edited; once the client accepts, no
    edit path calls it, so the accepted invoice keeps what they saw."""
    invoice.businessSnapshot = business_snapshot(invoice.project.organization)
    invoice.clientSnapshot = client_snapshot(db.get(User, invoice.invoiceAssignedTo))
