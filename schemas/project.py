from pydantic import BaseModel, ConfigDict, Field
from uuid import UUID
from datetime import datetime
from typing import Literal

from schemas.user import UserOut


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

    model_config = ConfigDict(from_attributes=True)


class ProjectCreate(BaseModel):
    projectName: str
    projectStatus: Literal[
        "Proposal", "Accepted", "Rejected", "Suggested Changes", "Planning", "Complete"
    ]
    projectStartDate: datetime
    projectEndDate: datetime
    vendorOnProject: UUID


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
