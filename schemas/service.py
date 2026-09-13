from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Literal

class ServiceOut(BaseModel):
    serviceId: UUID
    serviceName: str
    projectAssociatedTo: UUID
    cuisine: list[str]
    religion: Literal['Hindu', 'Muslim', "Christian"]
    serviceDate: datetime
    guestCount: int
    serviceType: Literal['Buffet', 'Plated', 'Family Style', 'Live Stations', 'Butler Passed']
    serviceVenue: Literal['Hotel', 'Country Club', 'Mueseum', 'Party Hall', 'Home', "Outdoor"]
    serviceEvent: Literal['breakfast', 'wedding Lunch', 'Wedding Dinner', 'Anniversary', 'birthday', 'cockatail hour', 'mehendi', 'haldi', 'ceremony refreshments', 'vidai', 'welcome dinner', 'welcome lunch', 'baarat', 'Walima', 'Graduation', 'house Warming', 'High tea']
    minPricePerPerson: float | None = None
    maxPricePerPerson: float | None = None

    class Config:
        from_attributes = True


class ServiceCreate(BaseModel):
    serviceName: str
    projectAssociatedTo: UUID
    cuisine: list[str]
    religion: Literal['Hindu', 'Muslim', "Christian"]
    serviceDate: datetime
    guestCount: int
    serviceType: Literal['Buffet', 'Plated', 'Family Style', 'Live Stations', 'Butler Passed']
    serviceVenue: Literal['Hotel', 'Country Club', 'Mueseum', 'Party Hall', 'Home', "Outdoor"]
    serviceEvent: Literal['breakfast', 'wedding Lunch', 'Wedding Dinner', 'Anniversary', 'birthday', 'cockatail hour', 'mehendi', 'haldi', 'ceremony refreshments', 'vidai', 'welcome dinner', 'welcome lunch', 'baarat', 'Walima', 'Graduation', 'house Warming', 'High tea']
    minPricePerPerson: float | None = None
    maxPricePerPerson: float | None = None


class ServiceUpdate(BaseModel):
    serviceName: str | None = None
    projectAssociatedTo: UUID | None = None
    cuisine: list[str] | None = None
    religion: Literal['Hindu', 'Muslim', "Christian"] | None = None
    serviceDate: datetime | None = None
    guestCount: int | None = None
    serviceType: Literal['Buffet', 'Plated', 'Family Style', 'Live Stations', 'Butler Passed'] | None = None
    serviceVenue: Literal['Hotel', 'Country Club', 'Mueseum', 'Party Hall', 'Home', "Outdoor"] | None = None
    serviceEvent: Literal['breakfast', 'wedding Lunch', 'Wedding Dinner', 'Anniversary', 'birthday', 'cockatail hour', 'mehendi', 'haldi', 'ceremony refreshments', 'vidai', 'welcome dinner', 'welcome lunch', 'baarat', 'Walima', 'Graduation', 'house Warming', 'High tea'] | None = None
    minPricePerPerson: float | None = None
    maxPricePerPerson: float | None = None
