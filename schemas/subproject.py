from decimal import Decimal
from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime

from models.choices import EventType, Religion, ServiceStyle, Venue
from schemas.project import ProjectOut


class SubprojectOut(BaseModel):
    subprojectId: UUID
    subprojectName: str
    projectAssociatedTo: UUID
    cuisine: list[str]
    religion: Religion | None = None
    subprojectDate: datetime
    guestCount: int
    subprojectType: ServiceStyle
    subprojectVenue: Venue
    subprojectEvent: EventType
    minPricePerPerson: Decimal | None = None
    maxPricePerPerson: Decimal | None = None
    project: ProjectOut
    effectiveTimezone: str
    # subprojectDate shown in the venue's timezone
    localSubprojectDate: datetime
    createdAt: datetime
    updatedAt: datetime

    model_config = ConfigDict(from_attributes=True)


class SubprojectCreate(BaseModel):
    subprojectName: str
    projectAssociatedTo: UUID
    cuisine: list[str]
    religion: Religion
    subprojectDate: datetime
    guestCount: int
    subprojectType: ServiceStyle
    subprojectVenue: Venue
    subprojectEvent: EventType
    minPricePerPerson: Decimal | None = None
    maxPricePerPerson: Decimal | None = None


class SubprojectUpdate(BaseModel):
    subprojectName: str | None = None
    cuisine: list[str] | None = None
    religion: Religion | None = None
    subprojectDate: datetime | None = None
    guestCount: int | None = None
    subprojectType: ServiceStyle | None = None
    subprojectVenue: Venue | None = None
    subprojectEvent: EventType | None = None
    minPricePerPerson: Decimal | None = None
    maxPricePerPerson: Decimal | None = None
