from sqlalchemy.orm import Session
from services.subproject import *
from fastapi import APIRouter, Depends, HTTPException
from models import Subproject, User
from schemas.subproject import SubprojectOut, SubprojectCreate, SubprojectUpdate
from database import get_db
from auth.dependencies import get_current_user, user_project_ids, require_permission, user_has_permission
from uuid import UUID

router = APIRouter()

@router.get("/subprojects",response_model=list[SubprojectOut])
def get_subprojects(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if user_has_permission(current_user, "subproject:view_all", db):
        return get_all_subprojects(db)
    return get_subprojects_by_project_ids(user_project_ids(current_user), db)

@router.get("/subprojects/projects/{project_id}", response_model=list[SubprojectOut])
def getSubprojectByProjectId(
    project_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    if not user_has_permission(current_user, "subproject:view_all", db) and project_id not in user_project_ids(current_user):
        raise HTTPException(status_code=403, detail="not authorized to view this project's subprojects")
    subprojects = get_all_subprojects_by_project_id(project_id, db)
    return subprojects

@router.get("/subprojects/{subproject_id}", response_model=SubprojectOut)
def get_subproject_by_id(
    subproject_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
     subproject = get_subproject_by_subproject_id(subproject_id, db)
     if subproject is None:
         raise HTTPException(status_code=404, detail="subproject not found")
     if not user_has_permission(current_user, "subproject:view_all", db) and subproject.projectAssociatedTo not in user_project_ids(current_user):
         raise HTTPException(status_code=403, detail="not authorized to view this subproject")
     return subproject

@router.post("/subprojects", response_model=SubprojectOut, dependencies=[Depends(require_permission("subproject:create"))])
def add_subproject(new_subproject: SubprojectCreate, db: Session = Depends(get_db)):
     created_subproject = add_new_subproject(new_subproject, db)
     return created_subproject

@router.patch("/subprojects/{subproject_id}", response_model=SubprojectOut, dependencies=[Depends(require_permission("subproject:update"))])
def update_subproject(subproject_id: UUID, updates: SubprojectUpdate, db: Session = Depends(get_db)):
    updated_subproject = update_subproject_by_subproject_id(subproject_id, updates, db)
    if updated_subproject is None:
        raise HTTPException(status_code=404, detail="subproject not found")
    return updated_subproject

@router.delete("/subprojects/{subproject_id}", status_code=204, dependencies=[Depends(require_permission("subproject:delete"))])
def delete_subproject(subproject_id: UUID, db: Session = Depends(get_db)):
    deleted_subproject = delete_subproject_by_subproject_id(subproject_id, db)
    if deleted_subproject is None:
        raise HTTPException(status_code=404, detail="subproject not found")
