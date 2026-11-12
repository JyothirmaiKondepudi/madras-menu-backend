from models import BillingInfo, Project, Subproject
from sqlalchemy import select
from sqlalchemy.orm import Session


def get_billing_info_by_subproject_id(subproject_id, db: Session):
    # subprojectId IS the primary key here — one row per subproject.
    return db.get(BillingInfo, subproject_id)

def billing_info_in_org_query(organization_id):
    """Every subproject summary in the caller's org, via subproject -> project."""
    return (
        select(BillingInfo)
        .join(Subproject, BillingInfo.subprojectId == Subproject.subprojectId)
        .join(Project, Subproject.projectAssociatedTo == Project.projectId)
        .where(Project.organizationId == organization_id)
    )


def billing_info_in_projects_query(project_ids):
    """For a non-vendor's GET /billing-info: every subproject's summary
    belonging to any project they're linked to, same scoping rule as
    services/billing_history.py's billing_history_in_projects_query."""
    return (
        select(BillingInfo)
        .join(Subproject, BillingInfo.subprojectId == Subproject.subprojectId)
        .where(Subproject.projectAssociatedTo.in_(project_ids))
    )


