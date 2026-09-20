from models import Project, Subproject
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

# shared by every query that returns a SubprojectOut, since it now nests
# project -> client / vendor
_WITH_PROJECT_AND_USERS = joinedload(Subproject.project).options(
    joinedload(Project.client),
    joinedload(Project.vendor),
)


def get_all_subprojects(db: Session):
    return db.execute(
        select(Subproject).options(_WITH_PROJECT_AND_USERS)
    ).scalars().all()

def get_subproject_by_subproject_id(subproject_id, db: Session):
    return db.get(Subproject, subproject_id, options=[_WITH_PROJECT_AND_USERS])

def add_new_subproject(new_subproject, db: Session):
    created_subproject = Subproject(
        subprojectName=new_subproject.subprojectName,
        projectAssociatedTo=new_subproject.projectAssociatedTo,
        cuisine=new_subproject.cuisine,
        religion=new_subproject.religion,
        subprojectDate=new_subproject.subprojectDate,
        guestCount=new_subproject.guestCount,
        subprojectType=new_subproject.subprojectType,
        subprojectVenue=new_subproject.subprojectVenue,
        subprojectEvent=new_subproject.subprojectEvent,
        minPricePerPerson=new_subproject.minPricePerPerson,
        maxPricePerPerson=new_subproject.maxPricePerPerson,
    )
    db.add(created_subproject)
    db.commit()
    db.refresh(created_subproject)
    return created_subproject

def update_subproject_by_subproject_id(subproject_id, updates, db: Session):
    subproject = db.get(Subproject, subproject_id)
    if subproject is None:
        return None

    for field, value in updates.model_dump(exclude_unset=True).items():
        setattr(subproject, field, value)

    db.commit()
    db.refresh(subproject)
    return subproject

def delete_subproject_by_subproject_id(subproject_id, db: Session):
    subproject = db.get(Subproject, subproject_id)
    if subproject is None:
        return None

    db.delete(subproject)
    db.commit()
    return subproject

def get_all_subprojects_by_project_id(project_id, db: Session):
    return db.execute(
        select(Subproject)
        .where(Subproject.projectAssociatedTo == project_id)
        .options(_WITH_PROJECT_AND_USERS)
    ).scalars().all()

def get_subprojects_by_project_ids(project_ids, db: Session):
    """For a non-vendor's GET /subprojects — every subproject belonging to
    any project they're linked to via user_projects."""
    return db.execute(
        select(Subproject)
        .where(Subproject.projectAssociatedTo.in_(project_ids))
        .options(_WITH_PROJECT_AND_USERS)
    ).scalars().all()
