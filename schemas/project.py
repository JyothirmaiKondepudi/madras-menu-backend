from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Literal

class ProjectOut(BaseModel):
    projectName: str
    projectId: UUID
    class Config:
        from_attributes = True



class ProjectCreate(BaseModel):
    projectName :str
    projectStatus: Literal['Proposal', 'Accepted', 'Rejected', 'Suggested Changes', 'Planning', 'Complete']
    projectStartDate:datetime 
    projectEndDate :datetime.now
    adminOnProject :UUID
    clientId :UUID
    project_invoice: UUID


class ProjectUpdate(BaseModel):
    projectName :str | None = None
    projectStatus: Literal['Proposal', 'Accepted', 'Rejected', 'Suggested Changes', 'Planning', 'Complete']
    projectStartDate:datetime 
    projectEndDate :datetime.now
    adminOnProject :UUID
    clientId :UUID
    project_invoice: UUID
