from model import Project
from sqlalchemy.orm import Session
from schemas.project import ProjectUpdate

# maps each ProjectUpdate/ProjectCreate field name to the ORM attribute it corresponds to
PROJECT_FIELD_MAP = {
    "projectName": "fullName",
    
}

def get_all_projects(db:Session):
    return db.query(Project).all()

def get_project_by_id(project_id, db:Session):
    return db.query(Project).get(project_id)

def add_new_Project(project, db:Session):
    existing_Project = db.query(Project).filter_by(projectId=project.).first()
    if existing_Project is not None:
        return None
    
    print(f" {Project.email} is not an exsiting Project. creating anew Project. ")
    created_Project = Project(
        fullName=Project.fullName,
        ProjectEmail=Project.email,
        ProjectPhoneNumber=Project.phoneNumber,
        preferredContact=Project.preferredContact,
        ProjectAddress=Project.address,
        ProjectRole=Project.role,
    )
    db.add(created_Project)
    db.commit()
    print(f"commited to databse succesfully")
    db.refresh(created_Project)
    return created_Project

def update_Project_by_Project_id(Project_id, updates: ProjectUpdate, db: Session):
    Project = db.query(Project).get(Project_id)
    if Project is None:
        return None

    for field, value in updates.model_dump(exclude_unset=True).items():
        setattr(Project, Project_FIELD_MAP[field], value)
    print(f"updated Project: {updates}")
    db.commit()
    db.refresh(Project)
    return Project

def delete_Project_by_Project_id(Project_id, db: Session):
    Project = db.query(Project).get(Project_id)
    if Project is None:
        return None

    db.delete(Project)
    db.commit()
    return Project