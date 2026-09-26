from sqlalchemy.orm import Session
from services.projects import *
from services.invoices import get_invoice_by_id
from fastapi import APIRouter, Depends, HTTPException
from models import Project, User
from schemas.project import ProjectOut, ProjectCreate, ProjectUpdate
from database import get_db
from auth.dependencies import get_current_user, user_project_ids, require_permission, user_has_permission
from uuid import UUID

router = APIRouter()

@router.get("/projects",response_model=list[ProjectOut])
def get_projects(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # vendor (or any future role granted project:view_all) sees every
    # project; anyone else only sees projects they're linked to via
    # user_projects (current_user.projects).
    if user_has_permission(current_user, "project:view_all", db):
        return get_all_projects(db)
    return current_user.projects

@router.post(
    "/projects/{project_id}/users/{user_id}",
    response_model=ProjectOut,
    dependencies=[Depends(require_permission("project:manage_users"))],
)
def add_project_user(project_id: UUID, user_id: UUID, db: Session = Depends(get_db)):
    project = add_user_to_project(project_id, user_id, db)
    if project is None:
        raise HTTPException(status_code=404, detail="project or user not found")
    return project

@router.patch(
    "/projects/{project_id}/final-invoice/{invoice_id}",
    response_model=ProjectOut,
    dependencies=[Depends(require_permission("project:set_final_invoice"))],
)
def set_project_final_invoice(project_id: UUID, invoice_id: UUID, db: Session = Depends(get_db)):
    """Records which invoice the client actually went ahead with — a
    project can have several (drafts/revisions), so this is never inferred
    automatically, only set explicitly here."""
    project = get_project_by_id(project_id, db)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    invoice = get_invoice_by_id(invoice_id, db)
    if invoice is None:
        raise HTTPException(status_code=404, detail="invoice not found")
    if invoice.projectAssociatedTo != project_id:
        raise HTTPException(status_code=400, detail="that invoice does not belong to this project")
    return set_final_invoice(project, invoice_id, db)

@router.get("/projects/users/{user_id}", response_model=list[ProjectOut])
def getProjectsByUserID(
    user_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    if not user_has_permission(current_user, "project:view_all", db) and user_id != current_user.userId:
        raise HTTPException(status_code=403, detail="cannot view another user's projects")
    return get_all_projects_by_user_id(user_id, db)

@router.get("/projects/{project_id}", response_model=ProjectOut)
def getProjectById(
    project_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
     project = get_project_by_id(project_id, db)
     if project is None:
         raise HTTPException(status_code=404, detail="project not found")
     if not user_has_permission(current_user, "project:view_all", db) and project_id not in user_project_ids(current_user):
         raise HTTPException(status_code=403, detail="not authorized to view this project")
     return project

@router.post("/projects", response_model=ProjectOut, dependencies=[Depends(require_permission("project:create"))])
def add_project(new_project: ProjectCreate, db: Session = Depends(get_db)):
     created_project = add_new_Project(new_project, db)
     if created_project is None:
         raise HTTPException(status_code=409, detail=f"failure creating a new project")
     return created_project

@router.patch("/projects/{project_id}", response_model=ProjectOut, dependencies=[Depends(require_permission("project:update"))])
def update_project(project_id: UUID, updates: ProjectUpdate, db: Session = Depends(get_db)):
    updated_project = update_project_by_project_id(project_id, updates, db)
    if updated_project is None:
        raise HTTPException(status_code=404, detail="project not found")
    return updated_project

@router.delete("/projects/{project_id}", status_code=204, dependencies=[Depends(require_permission("project:delete"))])
def delete_project(project_id: UUID, db: Session = Depends(get_db)):
    deleted_project = delete_Project_by_Project_id(project_id, db)
    if deleted_project is None:
        raise HTTPException(status_code=404, detail="project not found")
