from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import Organization, User
from schemas.organizations import (
    OrganizationOut,
    OrganizationCreate,
    OrganizationUpdate,
)
from auth.dependencies import get_current_user
from services.organizations import (
    get_organizations,
    create_new_org,
    get_org_info_by_id,
    update_org_info_by_id,
    delete_org_by_org_id,
)
from auth.dependencies import (
    get_current_user,
    user_project_ids,
    require_permission,
    user_has_permission,
)

router = APIRouter()


@router.get(
    "/organizations/all",
    response_model=list[OrganizationOut],
    dependencies=[Depends(require_permission("org:view_all"))],
)
def get_all_organizations(db: Session = Depends(get_db)):
    return get_organizations(db)


@router.post(
    "/organizations",
    response_model=OrganizationOut,
    dependencies=[Depends(require_permission("org:create"))],
)
def create_new_organization(
    new_Org: OrganizationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    created_org = create_new_org(new_Org, db)
    if created_org is None:
        raise HTTPException(
            status_code=409,
            detail=f"Organization with {new_Org.orgEmail} already exists",
        )
    return created_org


@router.get("/organizations/{org_id}", response_model=OrganizationOut)
def get_org_by_id(
    org_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if (
        not user_has_permission(current_user, "org:view_all", db)
        and org_id != current_user.userOrg
    ):
        raise HTTPException(status_code=403, detail="cannot view another org's profile")
    org_info = get_org_info_by_id(org_id, db)
    if org_info is None:
        raise HTTPException(
            status_code=404, detail=f"organization with id {org_id} does not exist"
        )
    return org_info


@router.patch(
    "/organizations/{org_id}",
    response_model=OrganizationOut,
    dependencies=[Depends(require_permission("org:update"))],
)
def update_org_info(
    org_id: UUID,
    updated_org: OrganizationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if (
        not user_has_permission(current_user, "org:view_all", db)
        and org_id != current_user.userOrg
    ):
        raise HTTPException(
            status_code=403, detail="cannot update another org's profile"
        )
    updated_org_info = update_org_info_by_id(org_id, updated_org, db)
    if updated_org_info is None:
        raise HTTPException(
            status_code=404, detail=f"org with id: {org_id} does not exist"
        )
    return updated_org_info


@router.delete(
    "/organizations/{org_id}",
    status_code=204,
    dependencies=[Depends(require_permission("org:delete"))],
)
def delete_user(org_id: UUID, db: Session = Depends(get_db)):
    deleted_user = delete_org_by_org_id(org_id, db)
    if deleted_user is None:
        raise HTTPException(status_code=404, detail="Org not found")
