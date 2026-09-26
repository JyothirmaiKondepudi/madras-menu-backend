from sqlalchemy.orm import Session
from services.billing_info import *
from services.subproject import get_subproject_by_subproject_id
from fastapi import APIRouter, Depends, HTTPException
from models import User
from schemas.billing_info import BillingInfoOut
from database import get_db
from auth.dependencies import get_current_user, user_project_ids, user_has_permission
from uuid import UUID

router = APIRouter()

@router.get("/billing-info", response_model=list[BillingInfoOut])
def get_billing_info(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if user_has_permission(current_user, "billing:view_all", db):
        return get_all_billing_info(db)
    return get_billing_info_by_project_ids(user_project_ids(current_user), db)

@router.get("/billing-info/subprojects/{subproject_id}", response_model=BillingInfoOut)
def get_billing_info_for_subproject(
    subproject_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    subproject = get_subproject_by_subproject_id(subproject_id, db)
    if subproject is None:
        raise HTTPException(status_code=404, detail="subproject not found")
    if not user_has_permission(current_user, "billing:view_all", db) and subproject.projectAssociatedTo not in user_project_ids(current_user):
        raise HTTPException(status_code=403, detail="not authorized to view this subproject's billing info")
    info = get_billing_info_by_subproject_id(subproject_id, db)
    if info is None:
        raise HTTPException(status_code=404, detail="no billing info recorded for this subproject yet")
    return info
