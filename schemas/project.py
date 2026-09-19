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
    adminOnProject: UUID | None = None
    clientId: UUID
    finalInvoiceId: UUID | None = None
    client: UserOut
    admin: UserOut | None = None

    model_config = ConfigDict(from_attributes=True)



class ProjectCreate(BaseModel):
    projectName :str
    projectStatus: Literal['Proposal', 'Accepted', 'Rejected', 'Suggested Changes', 'Planning', 'Complete']
    projectStartDate:datetime 
    projectEndDate :datetime
    adminOnProject :UUID
    clientId :UUID


class ProjectUpdate(BaseModel):
    projectName :str | None = None
    projectStatus: Literal['Proposal', 'Accepted', 'Rejected', 'Suggested Changes', 'Planning', 'Complete'] | None = None
    projectStartDate: datetime | None = None
    projectEndDate: datetime | None = None
    adminOnProject: UUID | None = None
    clientId: UUID | None = None
