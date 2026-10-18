from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import Organization, User
from services.listing import Listing, Page, paginate
from schemas.organizations import (
    OrganizationOut,
    OrganizationCreate,
    OrganizationUpdate,
)
from auth.dependencies import get_current_user
from services.organizations import (
    organizations_query,
    create_new_org,
    get_org_info_by_id,
    update_org_info_by_id,
    get_user_count,
    delete_org_by_org_id,
    get_project_count,
)
from auth.dependencies import (
    ensure_own_or_permission,
    get_current_user,
    require_permission,
)

router = APIRouter()


ORGANIZATION_SORTS = {
    "orgName": Organization.orgName,
    "createdAt": Organization.orgCreatedAt,
}


@router.get(
    "/organizations",
    response_model=Page[OrganizationOut],
    dependencies=[Depends(require_permission("org:view_all"))],
)
def get_all_organizations(listing: Listing, db: Session = Depends(get_db)):
    return paginate(
        db, organizations_query(), listing, ORGANIZATION_SORTS, "orgName", Organization.orgId
    )


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
    db.commit()
    return created_org


@router.get("/organizations/{org_id}", response_model=OrganizationOut)
def get_org_by_id(
    org_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_own_or_permission(
        current_user,
        org_id == current_user.userOrg,
        "org:view_all",
        db,
        "cannot view another org's profile",
    )
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
    ensure_own_or_permission(
        current_user,
        org_id == current_user.userOrg,
        "org:view_all",
        db,
        "cannot update another org's profile",
    )
    updated_org_info = update_org_info_by_id(org_id, updated_org, db)
    if updated_org_info is None:
        raise HTTPException(
            status_code=404, detail=f"org with id: {org_id} does not exist"
        )
    db.commit()
    return updated_org_info


@router.delete(
    "/organizations/{org_id}",
    status_code=204,
    dependencies=[Depends(require_permission("org:delete"))],
)
def delete_user(org_id: UUID, db: Session = Depends(get_db)):
    user_count = get_user_count(org_id, db)
    if user_count:
        raise HTTPException(
            status_code=409,
            detail=f"This organization has {user_count} users associated to it. Please delete them first.",
        )
    project_count = get_project_count(org_id, db)
    if project_count:
        raise HTTPException(
            status_code=409,
            detail=f"This organization has {project_count} projects associated to it. Please delete them first.",
        )
    deleted_user = delete_org_by_org_id(org_id, db)
    if deleted_user is None:
        raise HTTPException(status_code=404, detail="Org not found")
    db.commit()
