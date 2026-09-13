from sqlalchemy.orm import Session
from services.projects import *
from fastapi import APIRouter, Depends, HTTPException
from model import Project
from schemas.project import ProjectOut, ProjectCreate, ProjectUpdate
from database import get_db
from uuid import UUID

router = APIRouter()

@router.get("/projects",response_model=list[ProjectOut])
def get_projects(db: Session= Depends(get_db)):
    projects = get_all_projects(db)
    return projects

@router.get("/projects/users/{user_id}", response_model=list[ProjectOut])
def getProjectsByUserID(user_id:UUID, db: Session=Depends(get_db)):
    return get_all_projects_by_user_id(user_id, db)

@router.get("/projects/{project_id}", response_model=ProjectOut)
def getProjectById(project_id:UUID, db:Session= Depends(get_db)):
     return get_project_by_id(project_id, db)

@router.post("/projects", response_model=ProjectOut)
def add_project(new_project: ProjectCreate, db:Session= Depends(get_db)):
     created_project = add_new_Project(new_project, db)
     if created_project is None:
         raise HTTPException(status_code=409, detail=f"failure creating a new project")
     return created_project

@router.patch("/projects/{project_id}", response_model=ProjectOut)
def update_project(project_id: UUID, updates: ProjectUpdate, db: Session = Depends(get_db)):
    updated_project = update_project_by_project_id(project_id, updates, db)
    if updated_project is None:
        raise HTTPException(status_code=404, detail="project not found")
    return updated_project

@router.delete("/projects/{project_id}", status_code=204)
def delete_project(project_id: UUID, db: Session = Depends(get_db)):
    deleted_project = delete_Project_by_Project_id(project_id, db)
    if deleted_project is None:
        raise HTTPException(status_code=404, detail="project not found")

