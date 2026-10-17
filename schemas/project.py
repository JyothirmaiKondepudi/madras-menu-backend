from pydantic import BaseModel, ConfigDict, Field, field_serializer
from uuid import UUID
from datetime import datetime
from typing import Literal

from auth.viewer import current_viewer
from schemas.user import UserOut
from services.timezones import IanaTimezone


class ProjectOut(BaseModel):
    projectId: UUID
    projectName: str
    projectStatus: Literal[
        "Proposal", "Accepted", "Rejected", "Suggested Changes", "Planning", "Complete"
    ]
    projectStartDate: datetime
    projectEndDate: datetime
    vendorOnProject: UUID | None = None
    finalInvoiceId: UUID | None = None
    vendor: UserOut | None = None
    # Read from the Project.users relationship (user_projects)
    clients: list[UserOut] = Field(default=[], validation_alias="users")
    projectTimezone: str | None = None
    effectiveTimezone: str
    # projectStartDate / projectEndDate shown in the venue's timezone
    localStartDate: datetime
    localEndDate: datetime
    createdAt: datetime
    updatedAt: datetime

    model_config = ConfigDict(from_attributes=True)

    # A client sees only themselves here, never the project's other clients
    # or their contact details (BE-13). Applies wherever a project is
    # nested too (invoices, subprojects). Vendors and admins see everyone.
    @field_serializer("clients", mode="wrap")
    def _hide_other_clients(self, clients: list[UserOut], handler):
        viewer = current_viewer()
        if viewer is not None and viewer[1] == "client":
            clients = [c for c in clients if c.userId == viewer[0]]
        return handler(clients)


class ProjectCreate(BaseModel):
    projectName: str
    projectStatus: Literal[
        "Proposal", "Accepted", "Rejected", "Suggested Changes", "Planning", "Complete"
    ]
    projectStartDate: datetime
    projectEndDate: datetime
    vendorOnProject: UUID
    # venue timezone when it isn't the org's; times without an offset are read in it
    projectTimezone: IanaTimezone | None = None


class ProjectUpdate(BaseModel):
    projectName: str | None = None
    projectStatus: (
        Literal[
            "Proposal",
            "Accepted",
            "Rejected",
            "Suggested Changes",
            "Planning",
            "Complete",
        ]
        | None
    ) = None
    projectStartDate: datetime | None = None
    projectEndDate: datetime | None = None
    vendorOnProject: UUID | None = None
    projectTimezone: IanaTimezone | None = None
