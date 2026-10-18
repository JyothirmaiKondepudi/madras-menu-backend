from sqlalchemy.orm import Session
from services.billing_info import (
    billing_info_in_org_query,
    billing_info_in_projects_query,
    get_billing_info_by_subproject_id,
)
from fastapi import APIRouter, Depends, HTTPException
from services.listing import Listing, Page, paginate
from models import BillingInfo, Subproject, User
from schemas.billing_info import BillingInfoOut
from database import get_db
from auth.dependencies import (
    ensure_project_access,
    get_current_user,
    load_subproject_in_org,
    user_has_permission,
    user_project_ids,
)
from uuid import UUID

router = APIRouter()

BILLING_INFO_SORTS = {
    "balanceDue": BillingInfo.balanceDue,
    "totalInvoiced": BillingInfo.totalInvoiced,
    "totalPaid": BillingInfo.totalPaid,
    "nextDueDate": BillingInfo.nextDueDate,
}


@router.get("/billing-info", response_model=Page[BillingInfoOut])
def get_billing_info(
    listing: Listing,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if user_has_permission(current_user, "billing:view_all", db):
        stmt = billing_info_in_org_query(current_user.userOrg)
    else:
        stmt = billing_info_in_projects_query(user_project_ids(current_user))
    return paginate(
        db, stmt, listing, BILLING_INFO_SORTS, "nextDueDate", BillingInfo.subprojectId
    )

@router.get("/subprojects/{subproject_id}/billing-info", response_model=BillingInfoOut)
def get_billing_info_for_subproject(
    subproject_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    subproject: Subproject = Depends(load_subproject_in_org),
):
    ensure_project_access(
        current_user,
        subproject.projectAssociatedTo,
        "billing:view_all",
        db,
        "not authorized to view this subproject's billing info",
    )
    info = get_billing_info_by_subproject_id(subproject_id, db)
    if info is None:
        raise HTTPException(status_code=404, detail="no billing info recorded for this subproject yet")
    return info
