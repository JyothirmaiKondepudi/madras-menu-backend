from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator
from uuid import UUID
from datetime import datetime

from models.choices import Diet, EventType, Religion, ServiceStyle, Venue
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
    venueName: str | None = None
    venueAddress: str | None = None
    diet: list[Diet] = []
    allergies: list[str] = []
    theme: str | None = None
    themeNotes: str | None = None
    project: ProjectOut
    effectiveTimezone: str
    # subprojectDate shown in the venue's timezone
    localSubprojectDate: datetime
    createdAt: datetime
    updatedAt: datetime

    model_config = ConfigDict(from_attributes=True)

    # Decimal inside the app, a plain JSON number on the way out: the
    # frontend only displays these, it never does arithmetic on them
    @field_serializer("minPricePerPerson", "maxPricePerPerson", when_used="json")
    def _decimal_as_number(self, value: Decimal | None) -> float | None:
        return None if value is None else float(value)


class SubprojectCreate(BaseModel):
    subprojectName: str
    projectAssociatedTo: UUID
    cuisine: list[str] = Field(default=[])
    religion: Religion | None = None
    subprojectDate: datetime
    guestCount: int
    subprojectType: ServiceStyle
    subprojectVenue: Venue
    subprojectEvent: EventType
    minPricePerPerson: Decimal | None = None
    maxPricePerPerson: Decimal | None = None
    venueName: str | None = None
    venueAddress: str | None = None
    diet: list[Diet] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)
    theme: str | None = None
    themeNotes: str | None = None


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
    venueName: str | None = None
    venueAddress: str | None = None
    diet: list[Diet] | None = None
    allergies: list[str] | None = None
    theme: str | None = None
    themeNotes: str | None = None

    # list fields: leaving one out keeps it, [] clears it, and an explicit
    # null is rejected so the column never holds NULL
    @field_validator("cuisine", "diet", "allergies")
    @classmethod
    def _list_cant_be_null(cls, value, info):
        if value is None:
            raise ValueError(f"{info.field_name} can't be null; send [] for none")
        return value

    # leaving it out keeps the date; an explicit null used to reach the
    # timezone conversion and crash with a 500
    @field_validator("subprojectDate")
    @classmethod
    def _date_cant_be_null(cls, value):
        if value is None:
            raise ValueError("an event must keep its date")
        return value
