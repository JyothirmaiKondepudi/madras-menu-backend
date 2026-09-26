from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime
from typing import Literal

from schemas.user import UserOut

class ProjectOut(BaseModel):
    projectId: UUID
    projectName: str
    projectStatus: Literal['Proposal', 'Accepted', 'Rejected', 'Suggested Changes', 'Planning', 'Complete']
    projectStartDate: datetime
    projectEndDate: datetime
    vendorOnProject: UUID | None = None
    clientId: UUID
    finalInvoiceId: UUID | None = None
    client: UserOut
    vendor: UserOut | None = None

    model_config = ConfigDict(from_attributes=True)



class ProjectCreate(BaseModel):
    projectName :str
    projectStatus: Literal['Proposal', 'Accepted', 'Rejected', 'Suggested Changes', 'Planning', 'Complete']
    projectStartDate:datetime
    projectEndDate :datetime
    vendorOnProject :UUID
    clientId :UUID


class ProjectUpdate(BaseModel):
    projectName :str | None = None
    projectStatus: Literal['Proposal', 'Accepted', 'Rejected', 'Suggested Changes', 'Planning', 'Complete'] | None = None
    projectStartDate: datetime | None = None
    projectEndDate: datetime | None = None
    vendorOnProject: UUID | None = None
    clientId: UUID | None = None
