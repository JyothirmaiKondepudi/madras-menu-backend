from models import Project, User
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
        vendorOnProject=newProject.vendorOnProject,
        clientId=newProject.clientId,
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

def set_final_invoice(project: Project, invoice_id, db: Session) -> Project:
    """Points project.finalInvoiceId at invoice_id. The caller (route layer)
    is responsible for confirming invoice_id actually exists and belongs
    to this project before calling this — this function just performs the
    write, matching how add_user_to_project separates "is this valid" from
    "make it so.\""""
    project.finalInvoiceId = invoice_id
    db.commit()
    db.refresh(project)
    return project

def add_user_to_project(project_id, user_id, db: Session):
    """Links an already-existing user to an already-existing project via
    user_projects — the "add an existing client" action. Returns None if
    either id doesn't exist. Idempotent: linking an already-linked user
    again is a no-op, not a conflict."""
    project = db.get(Project, project_id)
    if project is None:
        return None
    user = db.get(User, user_id)
    if user is None:
        return None

    if user not in project.users:
        project.users.append(user)
        db.commit()
        db.refresh(project)
    return project
