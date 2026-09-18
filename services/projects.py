from models import Project
from sqlalchemy import select
from sqlalchemy.orm import Session
from schemas.project import ProjectUpdate


def get_all_projects(db:Session):
    return db.execute(select(Project)).scalars().all()

def get_project_by_id(project_id, db:Session):
    return db.get(Project, project_id)

def add_new_Project(newProject, db:Session):

    created_Project = Project(
        projectName=newProject.projectName,
        projectStatus=newProject.projectStatus,
        projectStartDate=newProject.projectStartDate,
        projectEndDate=newProject.projectEndDate,
        adminOnProject=newProject.adminOnProject,
        clientId=newProject.clientId,
        project_invoice=newProject.project_invoice,
    )
    db.add(created_Project)
    db.commit()
    print(f"commited to database succesfully")
    db.refresh(created_Project)
    return created_Project

def update_project_by_project_id(project_id, updates: ProjectUpdate, db: Session):
    project = db.get(Project, project_id)
    if project is None:
        return None

    for field, value in updates.model_dump(exclude_unset=True).items():
        setattr(project, field, value)

    db.commit()
    db.refresh(project)
    return project

def delete_Project_by_Project_id(project_id, db: Session):
    project = db.get(Project, project_id)
    if project is None:
        return None

    db.delete(project)
    db.commit()
    return project

def get_all_projects_by_user_id(user_id, db:Session):
    return db.execute(
        select(Project).where(Project.clientId == user_id)
    ).scalars().all()
