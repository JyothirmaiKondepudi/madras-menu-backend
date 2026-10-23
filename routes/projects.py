import logging

from sqlalchemy.orm import Session
from services.projects import (
    add_new_Project,
    add_user_to_project,
    delete_Project_by_Project_id,
    projects_for_user_query,
    projects_in_org_query,
    get_invoice_count,
    get_sub_project_count,
    set_final_invoice,
    update_project_by_project_id,
)
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from models import Project, User, Invoice
from schemas.project import FollowUpCreate, ProjectOut, ProjectCreate, ProjectUpdate
from schemas.project_creation import NewProject
from schemas.project_includes import ProjectWithIncludesOut
from services.invoice_document import InvoiceDocumentError
from services.invoices import regenerate_pdf
from services.project_creation import ProjectCreationError, create_full_project
from schemas.timeline import TimelineEntryOut
from services.project_includes import INCLUDES, parse_includes, with_includes
from services.timeline import describe_payment, project_timeline_query, record_follow_up
from database import get_db
from auth.dependencies import (
    ensure_own_or_permission,
    ensure_project_access,
    get_current_user,
    load_invoice_in_org,
    load_project_in_org,
    load_user_in_org,
    load_vendor_in_org,
    require_permission,
    user_has_permission,
)
from uuid import UUID

from services.listing import Listing, Page, paginate

router = APIRouter()
logger = logging.getLogger("uvicorn.error")


PROJECT_SORTS = {
    "projectName": Project.projectName,
    "projectStatus": Project.projectStatus,
    "projectStartDate": Project.projectStartDate,
    "projectEndDate": Project.projectEndDate,
    "createdAt": Project.createdAt,
}
ProjectStatus = ProjectOut.model_fields["projectStatus"].annotation


IncludeParam = Query(
    None, description=f"comma-separated, any of: {', '.join(INCLUDES)}"
)


def _list_projects(db, stmt, listing, status, start_from, start_to, search, include, current_user):
    if status is not None:
        stmt = stmt.where(Project.projectStatus == status)
    if start_from is not None:
        stmt = stmt.where(Project.projectStartDate >= start_from)
    if start_to is not None:
        stmt = stmt.where(Project.projectStartDate <= start_to)
    if search:
        stmt = stmt.where(Project.projectName.ilike(f"%{search}%"))
    includes = parse_includes(include)
    page = paginate(db, stmt, listing, PROJECT_SORTS, "-createdAt", Project.projectId)
    page["items"] = with_includes(db, page["items"], includes, current_user)
    return page


@router.get("/projects", response_model=Page[ProjectWithIncludesOut])
def get_projects(
    listing: Listing,
    status: ProjectStatus | None = None,
    start_from: datetime | None = Query(None, alias="startFrom"),
    start_to: datetime | None = Query(None, alias="startTo"),
    search: str | None = Query(None, description="part of the project name"),
    include: str | None = IncludeParam,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # vendor (or any future role granted project:view_all) sees every
    # project in their OWN organization; anyone else only sees projects
    # they're linked to via user_projects.
    if user_has_permission(current_user, "project:view_all", db):
        stmt = projects_in_org_query(current_user.userOrg)
    else:
        stmt = projects_for_user_query(current_user.userId)
    return _list_projects(
        db, stmt, listing, status, start_from, start_to, search, include, current_user
    )


@router.post(
    "/projects/{project_id}/users/{user_id}",
    response_model=ProjectOut,
    dependencies=[Depends(require_permission("project:manage_users"))],
)
def add_project_user(
    project_id: UUID,
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    user: User = Depends(load_user_in_org),
    project: Project = Depends(load_project_in_org),
):
    updated_project = add_user_to_project(
        project, user, db, actor_id=current_user.userId
    )
    if updated_project is None:
        raise HTTPException(status_code=404, detail="project or user not found")
    db.commit()
    return updated_project


@router.patch(
    "/projects/{project_id}/final-invoice/{invoice_id}",
    response_model=ProjectOut,
    dependencies=[Depends(require_permission("project:set_final_invoice"))],
)
def set_project_final_invoice(
    project_id: UUID,
    invoice_id: UUID,
    db: Session = Depends(get_db),
    invoice: Invoice = Depends(load_invoice_in_org),
    project: Project = Depends(load_project_in_org),
):
    """Records which invoice the client actually went ahead with — a
    project can have several (drafts/revisions), so this is never inferred
    automatically, only set explicitly here."""
    if invoice.projectAssociatedTo != project_id:
        raise HTTPException(
            status_code=400, detail="that invoice does not belong to this project"
        )
    updated_project = set_final_invoice(project, invoice_id, db)
    db.commit()
    return updated_project


@router.get("/users/{user_id}/projects", response_model=Page[ProjectWithIncludesOut])
def getProjectsByUserID(
    user_id: UUID,
    listing: Listing,
    status: ProjectStatus | None = None,
    start_from: datetime | None = Query(None, alias="startFrom"),
    start_to: datetime | None = Query(None, alias="startTo"),
    search: str | None = Query(None, description="part of the project name"),
    include: str | None = IncludeParam,
    db: Session = Depends(get_db),
    user: User = Depends(load_user_in_org),
    current_user: User = Depends(get_current_user),
):
    ensure_own_or_permission(
        current_user,
        user_id == current_user.userId,
        "project:view_all",
        db,
        "cannot view another user's projects",
    )
    stmt = projects_for_user_query(user_id)
    return _list_projects(
        db, stmt, listing, status, start_from, start_to, search, include, current_user
    )


@router.get("/projects/{project_id}", response_model=ProjectWithIncludesOut)
def getProjectById(
    project_id: UUID,
    include: str | None = IncludeParam,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    project: Project = Depends(load_project_in_org),
):
    ensure_project_access(
        current_user,
        project_id,
        "project:view_all",
        db,
        "not authorized to view this project",
    )
    [with_extras] = with_includes(db, [project], parse_includes(include), current_user)
    return with_extras


@router.post(
    "/projects",
    response_model=ProjectOut,
    dependencies=[Depends(require_permission("project:create"))],
)
def add_project(
    new_project: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    load_vendor_in_org(new_project.vendorOnProject, current_user, db)
    created_project = add_new_Project(
        new_project,
        db,
        organization_id=current_user.userOrg,
        actor_id=current_user.userId,
    )
    if created_project is None:
        raise HTTPException(status_code=409, detail=f"failure creating a new project")
    db.commit()
    return created_project


@router.patch(
    "/projects/{project_id}",
    response_model=ProjectOut,
    dependencies=[Depends(require_permission("project:update"))],
)
def update_project(
    project_id: UUID,
    updates: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    project: Project = Depends(load_project_in_org),
):
    if updates.vendorOnProject is not None:
        load_vendor_in_org(updates.vendorOnProject, current_user, db)
    updated_project = update_project_by_project_id(project_id, updates, db)
    if updated_project is None:
        raise HTTPException(status_code=404, detail="project not found")
    db.commit()
    return updated_project


@router.delete(
    "/projects/{project_id}",
    status_code=204,
    dependencies=[Depends(require_permission("project:delete"))],
)
def delete_project(
    project_id: UUID,
    db: Session = Depends(get_db),
    project: Project = Depends(load_project_in_org),
):
    sub_projects = get_sub_project_count(project_id, db)
    if sub_projects > 0:
        raise HTTPException(
            status_code=409,
            detail=f"This project has {sub_projects} sub projects. Please delete them first.",
        )
    invoice_count = get_invoice_count(project_id, db)
    if invoice_count > 0:
        raise HTTPException(
            status_code=409,
            detail=f"This project has {invoice_count} invoices. Please delete them first.",
        )
    deleted_project = delete_Project_by_Project_id(project_id, db)
    if deleted_project is None:
        raise HTTPException(status_code=404, detail="project not found")
    db.commit()


# --- activity timeline and follow-ups (BE-14) ---------------------------------
# Vendor-only for now: the timeline includes internal entries (deleted
# invoices, voided payments and their reasons). What clients see is BE-12's
# decision.


@router.get(
    "/projects/{project_id}/activity",
    response_model=Page[TimelineEntryOut],
    dependencies=[Depends(require_permission("project:view_all"))],
)
def get_project_activity(
    project_id: UUID,
    listing: Listing,
    db: Session = Depends(get_db),
    project: Project = Depends(load_project_in_org),
):
    timeline = project_timeline_query(project_id)
    columns = timeline.selected_columns
    page = paginate(
        db,
        timeline,
        listing,
        {"occurredAt": columns.occurredAt},
        "-occurredAt",
        columns.id,
        entities=False,
    )
    page["items"] = [describe_payment(entry) for entry in page["items"]]
    return page


@router.post(
    "/projects/{project_id}/follow-ups",
    response_model=ProjectOut,
    dependencies=[Depends(require_permission("project:update"))],
)
def add_follow_up(
    project_id: UUID,
    body: FollowUpCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    project: Project = Depends(load_project_in_org),
):
    updated_project = record_follow_up(
        project, body.note, body.nextFollowUpAt, db, actor_id=current_user.userId
    )
    db.commit()
    return updated_project


# --- the whole project in one call (BE-06) ---------------------------------------


@router.post(
    "/projects/full",
    response_model=ProjectWithIncludesOut,
    dependencies=[Depends(require_permission("project:create"))],
)
def create_project_with_details(
    body: NewProject,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Creates the client (or reuses theirs, found by email), the project,
    its subprojects and an optional first invoice in one transaction: if any
    part fails, nothing is saved. Returns the project with everything
    included."""
    # every permission the separate endpoints would need, checked before
    # anything is created
    needed = ["user:create", "project:manage_users"]
    if body.subprojects:
        needed.append("subproject:create")
    if body.invoice is not None:
        needed.append("invoice:create")
    missing = [p for p in needed if not user_has_permission(current_user, p, db)]
    if missing:
        raise HTTPException(status_code=403, detail=f"missing required permission: {', '.join(missing)}")
    if body.project.vendorOnProject is not None:
        load_vendor_in_org(body.project.vendorOnProject, current_user, db)

    try:
        project, invoice = create_full_project(body, db, current_user)
    except ProjectCreationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    except InvoiceDocumentError as exc:
        raise HTTPException(status_code=422, detail=f"invoice: {exc}")
    db.commit()

    if invoice is not None:
        # after the commit, like POST /invoices: a failed PDF doesn't undo
        # the project, and the download route regenerates it
        try:
            regenerate_pdf(invoice, db)
        except Exception:
            logger.exception("PDF generation failed for invoice %s", invoice.invoiceId)
    [created] = with_includes(db, [project], {"subprojects", "invoices", "billing"}, current_user)
    return created

