from schemas.billing_info import BillingInfoOut
from schemas.invoice import InvoiceSummaryOut
from schemas.project import ProjectOut
from schemas.subproject import SubprojectSummaryOut


class ProjectWithIncludesOut(ProjectOut):
    """A project plus whatever ?include= asked for (BE-08b). A field is null
    when it wasn't requested, and [] when it was but there's nothing."""

    subprojects: list[SubprojectSummaryOut] | None = None
    invoices: list[InvoiceSummaryOut] | None = None
    # the per-event billing summaries, as GET /subprojects/{id}/billing-info
    # returns them; project-level invoices have none (they're in invoices)
    billing: list[BillingInfoOut] | None = None
