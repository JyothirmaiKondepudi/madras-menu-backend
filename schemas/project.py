from pydantic import BaseModel
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
    project_invoice: UUID | None = None
    client: UserOut
    admin: UserOut | None = None

    class Config:
        from_attributes = True



class ProjectCreate(BaseModel):
    projectName :str
    projectStatus: Literal['Proposal', 'Accepted', 'Rejected', 'Suggested Changes', 'Planning', 'Complete']
    projectStartDate:datetime 
    projectEndDate :datetime
    adminOnProject :UUID
    clientId :UUID
    project_invoice: UUID | None = None


class ProjectUpdate(BaseModel):
    projectName :str | None = None
    projectStatus: Literal['Proposal', 'Accepted', 'Rejected', 'Suggested Changes', 'Planning', 'Complete']
    projectStartDate:datetime 
    projectEndDate :datetime
    adminOnProject :UUID
    clientId :UUID
    project_invoice: UUID | None = None
