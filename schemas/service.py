from pydantic import BaseModel
from uuid import UUID

class ServciceOut(BaseModel):
    serviceId:UUID
    serviceName: str
    cuisine: str

    class Config:
        from_attributes = True