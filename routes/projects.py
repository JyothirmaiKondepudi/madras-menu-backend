from sqlalchemy.orm import Session
from services.projects import (
    add_new_Project,
    add_user_to_project,
    delete_Project_by_Project_id,
    projects_for_user_query,
    projects_in_org_query,
    get_invoice_count,
    get_project_by_id,
    get_sub_project_count,
    set_final_invoice,
    update_project_by_project_id,
)
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from models import Project, User, Invoice
from schemas.project import ProjectOut, ProjectCreate, ProjectUpdate
from database import get_db
from auth.dependencies import (
    get_current_user,
    user_project_ids,
    require_permission,
    user_has_permission,
    load_project_in_org,
    load_user_in_org,
    load_invoice_in_org,
)
from uuid import UUID

from services.listing import Listing, Page, paginate

router = APIRouter()


PROJECT_SORTS = {
    "projectName": Project.projectName,
    "projectStatus": Project.projectStatus,
    "projectStartDate": Project.projectStartDate,
    "projectEndDate": Project.projectEndDate,
    "createdAt": Project.createdAt,
}
ProjectStatus = ProjectOut.model_fields["projectStatus"].annotation


def _list_projects(db, stmt, listing, status, start_from, start_to, search):
    if status is not None:
        stmt = stmt.where(Project.projectStatus == status)
    if start_from is not None:
        stmt = stmt.where(Project.projectStartDate >= start_from)
    if start_to is not None:
        stmt = stmt.where(Project.projectStartDate <= start_to)
    if search:
        stmt = stmt.where(Project.projectName.ilike(f"%{search}%"))
    return paginate(db, stmt, listing, PROJECT_SORTS, "-createdAt", Project.projectId)


@router.get("/projects", response_model=Page[ProjectOut])
def get_projects(
    listing: Listing,
    status: ProjectStatus | None = None,
    start_from: datetime | None = Query(None, alias="startFrom"),
    start_to: datetime | None = Query(None, alias="startTo"),
    search: str | None = Query(None, description="part of the project name"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # vendor (or any future role granted project:view_all) sees every
    # project in their OWN organization; anyone else only sees projects
    # they're linked to via user_projects.
    if user_has_permission(current_user, "project:view_all", db):
        stmt = projects_in_org_query(current_user.userOrg)
    else:
        stmt = projects_for_user_query(current_user.userId)
    return _list_projects(db, stmt, listing, status, start_from, start_to, search)


@router.post(
    "/projects/{project_id}/users/{user_id}",
    response_model=ProjectOut,
    dependencies=[Depends(require_permission("project:manage_users"))],
)
def add_project_user(
    project_id: UUID,
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    user: User = Depends(load_user_in_org),
    project: Project = Depends(load_project_in_org),
):
    updated_project = add_user_to_project(
        project, user, db, actor_id=current_user.userId
    )
    if updated_project is None:
        raise HTTPException(status_code=404, detail="project or user not found")
    db.commit()
    return updated_project


@router.patch(
    "/projects/{project_id}/final-invoice/{invoice_id}",
    response_model=ProjectOut,
    dependencies=[Depends(require_permission("project:set_final_invoice"))],
)
def set_project_final_invoice(
    project_id: UUID,
    invoice_id: UUID,
    db: Session = Depends(get_db),
    invoice: Invoice = Depends(load_invoice_in_org),
    project: Project = Depends(load_project_in_org),
):
    """Records which invoice the client actually went ahead with — a
    project can have several (drafts/revisions), so this is never inferred
    automatically, only set explicitly here."""
    if invoice.projectAssociatedTo != project_id:
        raise HTTPException(
            status_code=400, detail="that invoice does not belong to this project"
        )
    updated_project = set_final_invoice(project, invoice_id, db)
    db.commit()
    return updated_project


@router.get("/users/{user_id}/projects", response_model=Page[ProjectOut])
def getProjectsByUserID(
    user_id: UUID,
    listing: Listing,
    status: ProjectStatus | None = None,
    start_from: datetime | None = Query(None, alias="startFrom"),
    start_to: datetime | None = Query(None, alias="startTo"),
    search: str | None = Query(None, description="part of the project name"),
    db: Session = Depends(get_db),
    user: User = Depends(load_user_in_org),
    current_user: User = Depends(get_current_user),
):
    if (
        not user_has_permission(current_user, "project:view_all", db)
        and user_id != current_user.userId
    ):
        raise HTTPException(
            status_code=403, detail="cannot view another user's projects"
        )
    stmt = projects_for_user_query(user_id)
    return _list_projects(db, stmt, listing, status, start_from, start_to, search)


@router.get("/projects/{project_id}", response_model=ProjectOut)
def getProjectById(
    project_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    project: Project = Depends(load_project_in_org),
):
    project_info = get_project_by_id(project_id, db)
    if project_info is None:
        raise HTTPException(status_code=404, detail="project not found")
    if not user_has_permission(
        current_user, "project:view_all", db
    ) and project_id not in user_project_ids(current_user):
        raise HTTPException(
            status_code=403, detail="not authorized to view this project"
        )
    return project_info


@router.post(
    "/projects",
    response_model=ProjectOut,
    dependencies=[Depends(require_permission("project:create"))],
)
def add_project(
    new_project: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    load_user_in_org(new_project.vendorOnProject, current_user, db)
    created_project = add_new_Project(
        new_project,
        db,
        organization_id=current_user.userOrg,
        actor_id=current_user.userId,
    )
    if created_project is None:
        raise HTTPException(status_code=409, detail=f"failure creating a new project")
    db.commit()
    return created_project


@router.patch(
    "/projects/{project_id}",
    response_model=ProjectOut,
    dependencies=[Depends(require_permission("project:update"))],
)
def update_project(
    project_id: UUID,
    updates: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    project: Project = Depends(load_project_in_org),
):
    if updates.vendorOnProject is not None:
        load_user_in_org(updates.vendorOnProject, current_user, db)
    updated_project = update_project_by_project_id(project_id, updates, db)
    if updated_project is None:
        raise HTTPException(status_code=404, detail="project not found")
    db.commit()
    return updated_project


@router.delete(
    "/projects/{project_id}",
    status_code=204,
    dependencies=[Depends(require_permission("project:delete"))],
)
def delete_project(
    project_id: UUID,
    db: Session = Depends(get_db),
    project: Project = Depends(load_project_in_org),
):
    sub_projects = get_sub_project_count(project_id, db)
    if sub_projects > 0:
        raise HTTPException(
            status_code=409,
            detail=f"This project has {sub_projects} sub projects. Please delete them first.",
        )
    invoice_count = get_invoice_count(project_id, db)
    if invoice_count > 0:
        raise HTTPException(
            status_code=409,
            detail=f"This project has {invoice_count} invoices. Please delete them first.",
        )
    deleted_project = delete_Project_by_Project_id(project_id, db)
    if deleted_project is None:
        raise HTTPException(status_code=404, detail="project not found")
    db.commit()
