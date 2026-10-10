from pydantic import BaseModel, ConfigDict, Field
from uuid import UUID
from datetime import datetime
from typing import Literal

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
