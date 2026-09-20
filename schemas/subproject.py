from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime
from typing import Literal

from schemas.project import ProjectOut

class SubprojectOut(BaseModel):
    subprojectId: UUID
    subprojectName: str
    projectAssociatedTo: UUID
    cuisine: list[str]
    religion: Literal['Hindu', 'Muslim', "Christian"]
    subprojectDate: datetime
    guestCount: int
    subprojectType: Literal['Buffet', 'Plated', 'Family Style', 'Live Stations', 'Butler Passed']
    subprojectVenue: Literal['Hotel', 'Country Club', 'Mueseum', 'Party Hall', 'Home', "Outdoor"]
    subprojectEvent: Literal['breakfast', 'wedding Lunch', 'Wedding Dinner', 'Anniversary', 'birthday', 'cockatail hour', 'mehendi', 'haldi', 'ceremony refreshments', 'vidai', 'welcome dinner', 'welcome lunch', 'baarat', 'Walima', 'Graduation', 'house Warming', 'High tea']
    minPricePerPerson: float | None = None
    maxPricePerPerson: float | None = None
    project: ProjectOut

    model_config = ConfigDict(from_attributes=True)



class SubprojectCreate(BaseModel):
    subprojectName: str
    projectAssociatedTo: UUID
    cuisine: list[str]
    religion: Literal['Hindu', 'Muslim', "Christian"]
    subprojectDate: datetime
    guestCount: int
    subprojectType: Literal['Buffet', 'Plated', 'Family Style', 'Live Stations', 'Butler Passed']
    subprojectVenue: Literal['Hotel', 'Country Club', 'Mueseum', 'Party Hall', 'Home', "Outdoor"]
    subprojectEvent: Literal['breakfast', 'wedding Lunch', 'Wedding Dinner', 'Anniversary', 'birthday', 'cockatail hour', 'mehendi', 'haldi', 'ceremony refreshments', 'vidai', 'welcome dinner', 'welcome lunch', 'baarat', 'Walima', 'Graduation', 'house Warming', 'High tea']
    minPricePerPerson: float | None = None
    maxPricePerPerson: float | None = None


class SubprojectUpdate(BaseModel):
    subprojectName: str | None = None
    projectAssociatedTo: UUID | None = None
    cuisine: list[str] | None = None
    religion: Literal['Hindu', 'Muslim', "Christian"] | None = None
    subprojectDate: datetime | None = None
    guestCount: int | None = None
    subprojectType: Literal['Buffet', 'Plated', 'Family Style', 'Live Stations', 'Butler Passed'] | None = None
    subprojectVenue: Literal['Hotel', 'Country Club', 'Mueseum', 'Party Hall', 'Home', "Outdoor"] | None = None
    subprojectEvent: Literal['breakfast', 'wedding Lunch', 'Wedding Dinner', 'Anniversary', 'birthday', 'cockatail hour', 'mehendi', 'haldi', 'ceremony refreshments', 'vidai', 'welcome dinner', 'welcome lunch', 'baarat', 'Walima', 'Graduation', 'house Warming', 'High tea'] | None = None
    minPricePerPerson: float | None = None
    maxPricePerPerson: float | None = None
