"""Invoice statuses and the moves allowed between them (ticket C7).

    Assigned ──accept──▶ Accepted ──paid in full──▶ Paid
        │                    ▲                         │
        └──reject──▶ Declined └──payment voided────────┘

Invoices always have a client, so they start as Assigned. The status only
changes through actions: the client accepting or rejecting, and payments
reaching (or, after a void, dropping below) the invoice amount. Nobody sets
it directly, so every change goes through change_invoice_status.
"""

INVOICE_STATUSES = ("Assigned", "Accepted", "Paid", "Declined")

# billed once the client accepts: these count toward billing_info and take payments
COUNTED_INVOICE_STATUSES = ("Accepted", "Paid")
# until the client accepts, the vendor can still reject, delete or move the
# invoice, or shift its due date
EDITABLE_INVOICE_STATUSES = ("Assigned",)

INVOICE_TRANSITIONS = {
    "Assigned": {"Accepted", "Declined"},
    "Accepted": {"Paid"},
    "Paid": {"Accepted"},
    "Declined": set(),  # final: a new invoice starts over
}


class InvoiceStatusError(ValueError):
    """The invoice can't move to that status from where it is."""


def change_invoice_status(invoice, new_status: str) -> None:
    if new_status not in INVOICE_TRANSITIONS[invoice.invoiceStatus]:
        raise InvoiceStatusError(
            f"{invoice.invoiceStatus} invoices can't be changed to {new_status}."
        )
    invoice.invoiceStatus = new_status
