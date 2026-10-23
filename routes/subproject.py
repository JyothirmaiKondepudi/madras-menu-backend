from sqlalchemy.orm import Session
from services.subproject import (
    subprojects_in_org_query,
    subprojects_in_project_query,
    subprojects_in_projects_query,
    add_new_subproject,
    delete_subproject_by_subproject_id,
    get_invoice_count_for_sub_project,
    update_subproject_by_subproject_id,
)
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from models.choices import EventType
from services.listing import Listing, Page, paginate
from models import Subproject, User, Project
from schemas.subproject import SubprojectOut, SubprojectCreate, SubprojectUpdate
from database import get_db
from auth.dependencies import (
    ensure_project_access,
    get_current_user,
    load_project_in_org,
    load_subproject_in_org,
    require_permission,
    user_has_permission,
    user_project_ids,
)
from uuid import UUID

router = APIRouter()


SUBPROJECT_SORTS = {
    "subprojectDate": Subproject.subprojectDate,
    "subprojectName": Subproject.subprojectName,
    "guestCount": Subproject.guestCount,
    "createdAt": Subproject.createdAt,
}


def _list_subprojects(db, stmt, listing, date_from, date_to, event_type):
    if date_from is not None:
        stmt = stmt.where(Subproject.subprojectDate >= date_from)
    if date_to is not None:
        stmt = stmt.where(Subproject.subprojectDate <= date_to)
    if event_type is not None:
        stmt = stmt.where(Subproject.subprojectEvent == event_type)
    return paginate(
        db, stmt, listing, SUBPROJECT_SORTS, "subprojectDate", Subproject.subprojectId
    )


@router.get("/subprojects", response_model=Page[SubprojectOut])
def get_subprojects(
    listing: Listing,
    date_from: datetime | None = Query(None, alias="dateFrom"),
    date_to: datetime | None = Query(None, alias="dateTo"),
    event_type: EventType | None = Query(None, alias="eventType"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if user_has_permission(current_user, "subproject:view_all", db):
        stmt = subprojects_in_org_query(current_user.userOrg)
    else:
        stmt = subprojects_in_projects_query(user_project_ids(current_user))
    return _list_subprojects(db, stmt, listing, date_from, date_to, event_type)


@router.get("/projects/{project_id}/subprojects", response_model=Page[SubprojectOut])
def getSubprojectByProjectId(
    project_id: UUID,
    listing: Listing,
    date_from: datetime | None = Query(None, alias="dateFrom"),
    date_to: datetime | None = Query(None, alias="dateTo"),
    event_type: EventType | None = Query(None, alias="eventType"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    project: Project = Depends(load_project_in_org),
):
    ensure_project_access(
        current_user,
        project_id,
        "subproject:view_all",
        db,
        "not authorized to view this project's subprojects",
    )
    stmt = subprojects_in_project_query(project_id)
    return _list_subprojects(db, stmt, listing, date_from, date_to, event_type)


@router.get("/subprojects/{subproject_id}", response_model=SubprojectOut)
def get_subproject_by_id(
    subproject_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    sub_project: Subproject = Depends(load_subproject_in_org),
):
    ensure_project_access(
        current_user,
        sub_project.projectAssociatedTo,
        "subproject:view_all",
        db,
        "not authorized to view this subproject",
    )
    return sub_project


@router.post(
    "/subprojects",
    response_model=SubprojectOut,
    dependencies=[Depends(require_permission("subproject:create"))],
)
def add_subproject(
    new_subproject: SubprojectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project_info = db.get(Project, new_subproject.projectAssociatedTo)
    if project_info is None or project_info.organizationId != current_user.userOrg:
        raise HTTPException(status_code=404, detail="project not found")
    created_subproject = add_new_subproject(
        new_subproject, db, actor_id=current_user.userId
    )
    db.commit()
    return created_subproject


@router.patch(
    "/subprojects/{subproject_id}",
    response_model=SubprojectOut,
    dependencies=[Depends(require_permission("subproject:update"))],
)
def update_subproject(
    subproject_id: UUID,
    updates: SubprojectUpdate,
    db: Session = Depends(get_db),
    sub_project: Subproject = Depends(load_subproject_in_org),
):
    updated_subproject = update_subproject_by_subproject_id(subproject_id, updates, db)
    if updated_subproject is None:
        raise HTTPException(status_code=404, detail="subproject not found")
    db.commit()
    return updated_subproject


@router.delete(
    "/subprojects/{subproject_id}",
    status_code=204,
    dependencies=[Depends(require_permission("subproject:delete"))],
)
def delete_subproject(
    subproject_id: UUID,
    db: Session = Depends(get_db),
    sub_project: Subproject = Depends(load_subproject_in_org),
):
    invoice_count = get_invoice_count_for_sub_project(subproject_id, db)
    if invoice_count > 0:
        raise HTTPException(
            status_code=409,
            detail=f"This sub project has {invoice_count} invoices. Please delete them first.",
        )
    deleted_subproject = delete_subproject_by_subproject_id(subproject_id, db)
    if deleted_subproject is None:
        raise HTTPException(status_code=404, detail="subproject not found")
    db.commit()
