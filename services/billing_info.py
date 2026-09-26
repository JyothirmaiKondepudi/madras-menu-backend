from models import BillingInfo, Subproject
from sqlalchemy import select
from sqlalchemy.orm import Session


def get_billing_info_by_subproject_id(subproject_id, db: Session):
    # subprojectId IS the primary key here — one row per subproject.
    return db.get(BillingInfo, subproject_id)

def get_all_billing_info(db: Session):
    return db.execute(select(BillingInfo)).scalars().all()

def get_billing_info_by_project_ids(project_ids, db: Session):
    """For a non-vendor's GET /billing-info — every subproject's summary
    belonging to any project they're linked to, same scoping rule as
    services/billing_history.py's get_billing_history_by_project_ids."""
    return db.execute(
        select(BillingInfo)
        .join(Subproject, BillingInfo.subprojectId == Subproject.subprojectId)
        .where(Subproject.projectAssociatedTo.in_(project_ids))
    ).scalars().all()
