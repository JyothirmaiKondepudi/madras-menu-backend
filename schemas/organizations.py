from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime


class OrganizationCreate(BaseModel):
    orgId: UUID
    orgName: str

    orgCreatedAt: datetime
    orgEmail: str
    orgDisabled: bool


class OrganizationOut(BaseModel):
    orgId: UUID | None = None
    orgName: str | None = None

    orgCreatedAt: datetime | None = None
    orgEmail: str | None = None
    orgDisabled: bool | None = None

    model_config = ConfigDict(from_attributes=True)


class OrganizationUpdate(BaseModel):
    orgName: str | None = None

    orgCreatedAt: datetime | None = None
    orgEmail: str | None = None
    orgDisabled: bool | None = None
