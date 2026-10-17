from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime

from services.timezones import IanaTimezone


class OrganizationCreate(BaseModel):
    orgId: UUID
    orgName: str
    orgEmail: str
    orgDisabled: bool
    # defaults to America/New_York when omitted
    orgTimezone: IanaTimezone | None = None


class OrganizationOut(BaseModel):
    orgId: UUID | None = None
    orgName: str | None = None

    orgCreatedAt: datetime | None = None
    orgEmail: str | None = None
    orgDisabled: bool | None = None
    orgTimezone: str | None = None

    model_config = ConfigDict(from_attributes=True)


class OrganizationUpdate(BaseModel):
    orgName: str | None = None
    orgEmail: str | None = None
    orgDisabled: bool | None = None
    orgTimezone: IanaTimezone | None = None
