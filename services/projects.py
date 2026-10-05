from models import Organization, Project, User, user_projects
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from schemas.project import ProjectUpdate
from services.account_activity import record_activity
from services.notifications import create_notification
from services.timezones import effective_timezone, to_instant


def get_all_projects(organization_id, db: Session):
    """All projects in the given organization."""
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
    # times without an offset are local to the venue: the project's timezone, else the org's
    timezone = newProject.projectTimezone or db.get(Organization, organization_id).orgTimezone
    created_Project = Project(
        projectName=newProject.projectName,
        projectStatus=newProject.projectStatus,
        projectStartDate=to_instant(newProject.projectStartDate, timezone),
        projectEndDate=to_instant(newProject.projectEndDate, timezone),
        vendorOnProject=newProject.vendorOnProject,
        organizationId=organization_id,
        projectTimezone=newProject.projectTimezone,
    )
    db.add(created_Project)
    db.commit()
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

    changes = updates.model_dump(exclude_unset=True)
    # apply a timezone change first, so dates in the same request are read in it
    if "projectTimezone" in changes:
        project.projectTimezone = changes.pop("projectTimezone")
    for field in ("projectStartDate", "projectEndDate"):
        if field in changes:
            changes[field] = to_instant(changes[field], effective_timezone(project))
    for field, value in changes.items():
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
    """Sets project.finalInvoiceId. The caller must validate the invoice
    belongs to this project."""
    project.finalInvoiceId = invoice_id
    db.commit()
    db.refresh(project)
    return project


def add_user_to_project(project: Project, user: User, db: Session, actor_id=None):
    """Links a user to a project via user_projects. The caller must check
    both are in its org. Idempotent: re-linking is a silent no-op."""

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
