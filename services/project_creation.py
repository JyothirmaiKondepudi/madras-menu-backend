"""Creating a whole project in one call (BE-06): the client, the project, its
subprojects and an optional first invoice.

Each step uses the same service as its own endpoint (POST /users, /projects,
/projects/{id}/users/{id}, /subprojects, /invoices), so the same rules apply.
Those services only flush; the route commits once at the end, so if any step
fails, nothing from the earlier steps is saved either.
"""

from sqlalchemy.orm import Session

from models import User
from schemas.invoice import InvoiceCreate
from schemas.project import ProjectCreate
from schemas.project_creation import NewProject, NewProjectClient
from schemas.subproject import SubprojectCreate
from schemas.user import UserCreate
from services.invoices import add_new_invoice
from services.projects import add_new_Project, add_user_to_project
from services.subproject import add_new_subproject
from services.users import add_new_user, get_user_by_email


class ProjectCreationError(Exception):
    """The request can't be carried out; status_code is the HTTP status."""

    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def find_or_create_client(client: NewProjectClient, db: Session, current_user: User) -> User:
    """The client with this email in the caller's organization, as it is;
    or a new client if nobody has the email."""
    existing = get_user_by_email(client.email, db)
    if existing is None:
        return add_new_user(
            UserCreate(
                fullName=client.fullName,
                email=client.email,
                phoneNumber=client.phoneNumber,
                preferredContact=client.preferredContact,
                address=client.address,
                role="client",
            ),
            db,
            created_by=current_user,
        )
    if existing.userOrg != current_user.userOrg:
        # emails are unique across organizations, and another org's user
        # can't be linked here
        raise ProjectCreationError(
            409, "This email belongs to a user in another organization."
        )
    if existing.userRole != "client":
        raise ProjectCreationError(
            409, "This email belongs to a staff account, not a client."
        )
    return existing


def create_full_project(body: NewProject, db: Session, current_user: User):
    """Returns (project, invoice or None). Flushes only: the caller commits."""
    actor = current_user.userId
    client = find_or_create_client(body.client, db, current_user)

    project = add_new_Project(
        ProjectCreate(
            **body.project.model_dump(exclude={"vendorOnProject"}),
            vendorOnProject=body.project.vendorOnProject or current_user.userId,
        ),
        db,
        organization_id=current_user.userOrg,
        actor_id=actor,
    )
    add_user_to_project(project, client, db, actor_id=actor)

    # ids in request order, so the invoice can point at one by position
    subproject_ids = []
    for subproject in body.subprojects:
        created = add_new_subproject(
            SubprojectCreate(**subproject.model_dump(), projectAssociatedTo=project.projectId),
            db,
            actor_id=actor,
        )
        subproject_ids.append(created.subprojectId)

    invoice = None
    if body.invoice is not None:
        index = body.invoice.subprojectIndex
        invoice = add_new_invoice(
            InvoiceCreate(
                **body.invoice.model_dump(exclude={"subprojectIndex"}),
                projectAssociatedTo=project.projectId,
                invoiceAssignedTo=client.userId,
                subprojectId=subproject_ids[index] if index is not None else None,
            ),
            db,
            actor_id=actor,
        )
    return project, invoice
