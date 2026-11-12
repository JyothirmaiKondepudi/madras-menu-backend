"""?include=subprojects,invoices,billing on project responses (BE-08b), so a
page can get its projects and their events, invoices and billing in one
request. Each include is one query for the whole page of projects, not one
per project.

Visibility is the same as on the dedicated endpoints: the caller can already
see these projects, which lets them see the projects' events and billing; a
caller without invoice:view_all (a client) sees only invoices billed to them,
as on GET /invoices.
"""

from collections import defaultdict

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from auth.access import user_has_permission
from models import BillingInfo, Invoice, Project, Subproject, User
from schemas.billing_info import BillingInfoOut
from schemas.invoice import InvoiceSummaryOut
from schemas.project_includes import ProjectWithIncludesOut
from schemas.subproject import SubprojectSummaryOut

INCLUDES = ("subprojects", "invoices", "billing")


def parse_includes(raw: str | None) -> set[str]:
    """"subprojects,invoices" -> {"subprojects", "invoices"}; 422 on anything
    it doesn't know."""
    if not raw:
        return set()
    requested = {part.strip() for part in raw.split(",") if part.strip()}
    unknown = requested - set(INCLUDES)
    if unknown:
        raise HTTPException(
            status_code=422,
            detail=f"Can't include {', '.join(sorted(unknown))}. Choose from: {', '.join(INCLUDES)}.",
        )
    return requested


def with_includes(
    db: Session, projects: list[Project], includes: set[str], current_user: User
) -> list[ProjectWithIncludesOut]:
    project_ids = [p.projectId for p in projects]
    found = {name: defaultdict(list) for name in includes}

    if "subprojects" in includes and project_ids:
        for subproject in db.scalars(
            select(Subproject)
            .where(Subproject.projectAssociatedTo.in_(project_ids))
            .order_by(Subproject.subprojectDate, Subproject.subprojectId)
        ):
            found["subprojects"][subproject.projectAssociatedTo].append(
                SubprojectSummaryOut.model_validate(subproject)
            )

    if "invoices" in includes and project_ids:
        stmt = select(Invoice).where(Invoice.projectAssociatedTo.in_(project_ids))
        if not user_has_permission(current_user, "invoice:view_all", db):
            stmt = stmt.where(Invoice.invoiceAssignedTo == current_user.userId)
        for invoice in db.scalars(stmt.order_by(Invoice.createdAt, Invoice.invoiceId)):
            found["invoices"][invoice.projectAssociatedTo].append(
                InvoiceSummaryOut.model_validate(invoice)
            )

    if "billing" in includes and project_ids:
        rows = db.execute(
            select(BillingInfo, Subproject.projectAssociatedTo)
            .join(Subproject, BillingInfo.subprojectId == Subproject.subprojectId)
            .where(Subproject.projectAssociatedTo.in_(project_ids))
            .order_by(Subproject.subprojectDate, Subproject.subprojectId)
        )
        for info, project_id in rows:
            found["billing"][project_id].append(BillingInfoOut.model_validate(info))

    return [
        ProjectWithIncludesOut.model_validate(project).model_copy(
            update={name: found[name][project.projectId] for name in includes}
        )
        for project in projects
    ]
