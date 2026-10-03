from models import Project, User, user_projects
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from schemas.project import ProjectUpdate
from services.account_activity import record_activity
from services.notifications import create_notification


def get_all_projects(organization_id, db: Session):
    """ "All projects" now means all projects in the caller's own
    organization — not literally every project in the database. Passing
    organization_id=None (a vendor not yet assigned to an org) matches
    only projects that are themselves org-less, never every tenant's."""
    return (
        db.execute(
            select(Project)
            .where(Project.organizationId == organization_id)
            .options(selectinload(Project.users))
        )
        .scalars()
        .all()
    )


def get_project_by_id(project_id, db: Session):
    return db.get(Project, project_id)


def add_new_Project(newProject, db: Session, organization_id=None, actor_id=None):

    created_Project = Project(
        projectName=newProject.projectName,
        projectStatus=newProject.projectStatus,
        projectStartDate=newProject.projectStartDate,
        projectEndDate=newProject.projectEndDate,
        vendorOnProject=newProject.vendorOnProject,
        organizationId=organization_id,
    )
    db.add(created_Project)
    db.commit()
    print(f"commited to database succesfully")
    db.refresh(created_Project)
    record_activity(
        db,
        activity_type="project_created",
        description=f'Project "{created_Project.projectName}" was created',
        project_id=created_Project.projectId,
        actor_id=actor_id,
    )
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


def get_all_projects_by_user_id(user_id, db: Session):
    """Projects the user is linked to via user_projects."""
    return (
        db.execute(
            select(Project)
            .join(user_projects, user_projects.c.project_id == Project.projectId)
            .where(user_projects.c.user_id == user_id)
            .options(selectinload(Project.users))
        )
        .scalars()
        .all()
    )


def set_final_invoice(project: Project, invoice_id, db: Session) -> Project:
    """Points project.finalInvoiceId at invoice_id. The caller (route layer)
    is responsible for confirming invoice_id actually exists and belongs
    to this project before calling this — this function just performs the
    write, matching how add_user_to_project separates "is this valid" from
    "make it so.\" """
    project.finalInvoiceId = invoice_id
    db.commit()
    db.refresh(project)
    return project


def add_user_to_project(project_id, user_id, db: Session, actor_id=None):
    """Links an already-existing user to an already-existing project via
    user_projects — the "add an existing client" action. Returns None if
    either id doesn't exist. Idempotent: linking an already-linked user
    again is a no-op, not a conflict — and not logged again either, since
    nothing actually happened the second time."""
    project = db.get(Project, project_id)
    if project is None:
        return None
    user = db.get(User, user_id)
    if user is None:
        return None

    if user not in project.users:
        existing_clients = list(project.users)
        project.users.append(user)
        db.commit()
        db.refresh(project)
        record_activity(
            db,
            activity_type="project_assigned",
            description=f'{user.fullName} was added to project "{project.projectName}"',
            project_id=project.projectId,
            actor_id=actor_id,
        )
        # Notify the vendor and the clients already on the project — never
        # the newly added user about their own addition.
        if (
            project.vendorOnProject is not None
            and project.vendorOnProject != user.userId
        ):
            create_notification(
                db,
                user_id=project.vendorOnProject,
                type="project_user_added",
                message=f'{user.fullName} was added to project "{project.projectName}"',
                related_user_id=user.userId,
            )
        for existing in existing_clients:
            create_notification(
                db,
                user_id=existing.userId,
                type="project_user_added",
                message=f'{user.fullName} was added to your project "{project.projectName}"',
                related_user_id=user.userId,
            )
    return project
