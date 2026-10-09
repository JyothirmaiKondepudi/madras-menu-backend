from models import BillingHistory, Project, Subproject, Invoice
from sqlalchemy import select, func, update
from uuid import UUID
from sqlalchemy.orm import Session, joinedload, selectinload
from services.account_activity import record_activity
from services.timezones import effective_timezone, to_instant

# shared by every query that returns a SubprojectOut, since it now nests
# project -> client / vendor
_WITH_PROJECT_AND_USERS = joinedload(Subproject.project).options(
    selectinload(Project.users),
    joinedload(Project.vendor),
)


def get_all_subprojects(organization_id, db: Session):
    """ "All subprojects" now means all subprojects in the caller's own
    organization — scoped by joining through Subproject's own project,
    same reasoning as get_all_invoices."""
    return (
        db.execute(
            select(Subproject)
            .join(Project, Subproject.projectAssociatedTo == Project.projectId)
            .where(Project.organizationId == organization_id)
            .options(_WITH_PROJECT_AND_USERS)
        )
        .scalars()
        .all()
    )


def get_subproject_by_subproject_id(subproject_id, db: Session):
    return db.get(Subproject, subproject_id, options=[_WITH_PROJECT_AND_USERS])


def add_new_subproject(new_subproject, db: Session, actor_id=None):
    # a time without an offset is local to the venue (the project's effective timezone)
    project = db.get(Project, new_subproject.projectAssociatedTo)
    created_subproject = Subproject(
        subprojectName=new_subproject.subprojectName,
        projectAssociatedTo=new_subproject.projectAssociatedTo,
        cuisine=new_subproject.cuisine,
        religion=new_subproject.religion,
        subprojectDate=to_instant(
            new_subproject.subprojectDate, effective_timezone(project)
        ),
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
    record_activity(
        db,
        activity_type="subproject_created",
        description=f'Subproject "{created_subproject.subprojectName}" was created',
        project_id=created_subproject.projectAssociatedTo,
        subproject_id=created_subproject.subprojectId,
        actor_id=actor_id,
    )
    return created_subproject


def _shift_due_dates(subproject_id, delta, db: Session) -> None:
    """The event moved, so its invoices' due dates move by the same amount,
    which keeps any date the vendor set by hand the same distance from the
    event. Invoices the client has accepted or paid keep their due date,
    the same ones that can't be deleted or moved."""
    live_payment = (
        select(BillingHistory.id)
        .where(
            BillingHistory.invoiceId == Invoice.invoiceId,
            BillingHistory.eventType == "Payment_Succeeded",
            BillingHistory.voidedAt.is_(None),
        )
        .exists()
    )
    db.execute(
        update(Invoice)
        .where(
            Invoice.subprojectId == subproject_id,
            Invoice.invoiceDeletedAt.is_(None),
            Invoice.dueDate.is_not(None),
            Invoice.invoiceStatus.in_(["Generated", "Assigned", "Pending"]),
            ~live_payment,
        )
        .values(dueDate=Invoice.dueDate + delta)
        .execution_options(synchronize_session=False)
    )


def update_subproject_by_subproject_id(subproject_id, updates, db: Session):
    subproject = db.get(Subproject, subproject_id)
    if subproject is None:
        return None

    old_date = subproject.subprojectDate
    changes = updates.model_dump(exclude_unset=True)
    if "subprojectDate" in changes:
        changes["subprojectDate"] = to_instant(
            changes["subprojectDate"], subproject.effectiveTimezone
        )
    for field, value in changes.items():
        setattr(subproject, field, value)

    if subproject.subprojectDate != old_date:
        _shift_due_dates(subproject_id, subproject.subprojectDate - old_date, db)

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


def get_invoice_count_for_sub_project(sub_project_id: UUID, db: Session):
    return db.scalar(
        select(func.count())
        .select_from(Invoice)
        .where(Invoice.subprojectId == sub_project_id)
        # soft-deleted invoices still block the delete in the database, so count them
        .execution_options(include_deleted=True)
    )


def get_all_subprojects_by_project_id(project_id, db: Session):
    return (
        db.execute(
            select(Subproject)
            .where(Subproject.projectAssociatedTo == project_id)
            .options(_WITH_PROJECT_AND_USERS)
        )
        .scalars()
        .all()
    )


def get_subprojects_by_project_ids(project_ids, db: Session):
    """For a non-vendor's GET /subprojects — every subproject belonging to
    any project they're linked to via user_projects."""
    return (
        db.execute(
            select(Subproject)
            .where(Subproject.projectAssociatedTo.in_(project_ids))
            .options(_WITH_PROJECT_AND_USERS)
        )
        .scalars()
        .all()
    )
