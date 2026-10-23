from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator, model_validator
from uuid import UUID
from typing import Literal

from schemas.project import ProjectOut

def _adjustment():
    return Field(
        default=None, ge=-100, le=100, max_digits=5, decimal_places=2,
        description="applied to the subtotal: -10 is a 10% discount, 5 a 5% surcharge",
    )


class LineItemIn(BaseModel):
    """A line on the invoice. With a sourceId (a rate card item for a
    service, an equipment item for equipment), name and unitPrice default to
    the catalog's; a custom line gives both."""

    kind: Literal["service", "equipment", "custom"]
    sourceId: UUID | None = None
    name: str | None = Field(default=None, min_length=1)
    quantity: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    unitPrice: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)

    @field_validator("sourceId")
    @classmethod
    def _custom_has_no_source(cls, value, info):
        if value is not None and info.data.get("kind") == "custom":
            raise ValueError("a custom line has no catalog source")
        return value


class LineItemOut(BaseModel):
    id: UUID
    position: int
    kind: str
    sourceId: UUID | None = None
    name: str
    quantity: Decimal
    unitPrice: Decimal
    pricingUnit: str | None = None
    lineTotal: Decimal

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("quantity", "unitPrice", "lineTotal", when_used="json")
    def _decimal_as_number(self, value: Decimal) -> float:
        return float(value)


class InvoiceSummaryOut(BaseModel):
    """An invoice without its project: for lists nested inside a project
    (GET /projects?include=invoices), where the project would only repeat."""

    invoiceId: UUID
    invoiceStatus: Literal["Assigned", "Accepted", "Paid", "Declined"]
    invoiceAmount: Decimal
    totalAmount: Decimal | None = None
    depositPercentage: Decimal | None = None
    invoiceAssignedTo: UUID
    projectAssociatedTo: UUID
    subprojectId: UUID | None = None
    createdAt: datetime
    updatedAt: datetime
    dueDate: datetime | None = None
    invoiceDeletedAt: datetime | None = None
    invoiceNumber: str | None = None
    currency: str = "USD"
    subtotalAmount: Decimal | None = None
    adjustmentPercentage: Decimal | None = None
    model_config = ConfigDict(from_attributes=True)

    # Decimal inside the app, a plain JSON number on the way out: the
    # frontend only displays these, it never does arithmetic on them
    @field_serializer(
        "invoiceAmount", "totalAmount", "depositPercentage", "subtotalAmount",
        "adjustmentPercentage", when_used="json",
    )
    def _decimal_as_number(self, value: Decimal | None) -> float | None:
        return None if value is None else float(value)


class InvoiceOut(InvoiceSummaryOut):
    project: ProjectOut
    # the full document; left out of the summary so project includes stay light
    lineItems: list[LineItemOut] = []
    legalTerms: str | None = None
    deliverables: str | None = None
    businessSnapshot: dict | None = None
    clientSnapshot: dict | None = None


class InvoiceFields(BaseModel):
    """Invoice fields shared by InvoiceCreate and the new-project request
    (schemas/project_creation.py), which creates the project, client and
    subprojects in the same call and so can't send their ids."""

    # no invoiceStatus: new invoices are always Assigned (services/invoice_status.py)
    # invoiceAmount isn't sent: it's totalAmount * depositPercentage / 100.
    # Send lineItems (totalAmount is then computed from them) or, for a single
    # amount without a breakdown, totalAmount; not both.
    lineItems: list[LineItemIn] | None = Field(default=None, min_length=1)
    adjustmentPercentage: Decimal | None = _adjustment()
    totalAmount: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    legalTerms: str | None = None
    deliverables: str | None = None
    depositPercentage: Decimal = Field(gt=0, le=100, max_digits=5, decimal_places=2)
    dueDate: datetime | None = None

    @model_validator(mode="after")
    def _total_or_line_items(self):
        # a model validator, not a field one: field validators skip fields
        # that were left out, and "neither was sent" is one of the cases
        has_lines = self.lineItems is not None
        if has_lines and self.totalAmount is not None:
            raise ValueError("send lineItems or totalAmount, not both: the total is computed from the lines")
        if not has_lines and self.totalAmount is None:
            raise ValueError("send lineItems, or totalAmount for an invoice without a breakdown")
        if not has_lines and self.adjustmentPercentage is not None:
            raise ValueError("adjustmentPercentage applies to line items")
        return self


class InvoiceCreate(InvoiceFields):
    invoiceAssignedTo: UUID
    projectAssociatedTo: UUID
    subprojectId: UUID | None = None


class InvoiceUpdate(BaseModel):
    # no invoiceStatus: it only changes through accept, reject and payments
    totalAmount: Decimal | None = Field(
        default=None, gt=0, max_digits=12, decimal_places=2
    )
    depositPercentage: Decimal | None = Field(
        default=None, gt=0, le=100, max_digits=5, decimal_places=2
    )
    invoiceAssignedTo: UUID | None = None
    subprojectId: UUID | None = None
    dueDate: datetime | None = None
    # the document: these can only change while the invoice is Assigned.
    # lineItems replaces every line; null for adjustmentPercentage removes it.
    lineItems: list[LineItemIn] | None = Field(default=None, min_length=1)
    adjustmentPercentage: Decimal | None = _adjustment()
    currency: str = Field(default=None, pattern=r"^[A-Z]{3}$")
    legalTerms: str | None = None
    deliverables: str | None = None

    # Leaving it out keeps the current client; an explicit null would try to
    # remove the client, which the NOT NULL column rejects (it was a 500).
    # Validators don't run on the default, so only an explicit null gets here.
    @field_validator("invoiceAssignedTo")
    @classmethod
    def _client_cant_be_removed(cls, value):
        if value is None:
            raise ValueError("an invoice must stay assigned to a client")
        return value
