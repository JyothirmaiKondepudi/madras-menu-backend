"""The request for creating a whole project in one call (BE-06): the client,
the project, its subprojects and an optional first invoice, saved together
or not at all. Its parts leave out the ids the server fills in as it creates
each one."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from schemas.invoice import InvoiceFields
from schemas.project import ProjectFields
from schemas.subproject import SubprojectFields
from schemas.user import _normalize_email


class NewProjectClient(BaseModel):
    """Who the project is for. Found by email: an existing client in the
    caller's organization is reused as is (their saved details aren't
    changed); otherwise a new client is created with these details."""

    email: str
    fullName: str
    phoneNumber: str | None = None
    preferredContact: Literal["email", "phone"] | None = None
    address: str | None = None

    _email_lowercase = field_validator("email")(_normalize_email)


class NewProjectDetails(ProjectFields):
    """The project itself: ProjectCreate with the vendor optional."""

    # defaults to the vendor making the request
    vendorOnProject: UUID | None = None


class NewProjectSubproject(SubprojectFields):
    """A subproject in a new-project request: SubprojectCreate without
    projectAssociatedTo, which the server fills in once the project exists."""


class NewProjectInvoice(InvoiceFields):
    """The first invoice in a new-project request: InvoiceCreate without the
    project, client and subproject ids, which the server fills in. It's
    billed to the request's client."""

    # which of the request's subprojects it's for, by position in the
    # subprojects list (0 = the first); leave out for an invoice on the
    # whole project, e.g. a deposit
    subprojectIndex: int | None = Field(default=None, ge=0)


class NewProject(BaseModel):
    """POST /projects/full: everything the project wizard collects, created
    together in one transaction (BE-06)."""

    client: NewProjectClient
    project: NewProjectDetails
    subprojects: list[NewProjectSubproject] = []
    invoice: NewProjectInvoice | None = None

    @model_validator(mode="after")
    def _invoice_subproject_exists(self):
        # checked here, before anything is created, because only the whole
        # request knows how many subprojects there are
        index = self.invoice.subprojectIndex if self.invoice else None
        if index is not None and index >= len(self.subprojects):
            raise ValueError(
                f"invoice.subprojectIndex {index} doesn't match a subproject: "
                f"this request has {len(self.subprojects)}"
            )
        return self
