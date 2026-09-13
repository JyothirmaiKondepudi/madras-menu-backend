from pydantic import BaseModel, ConfigDict
from datetime import datetime

class MenuItemOut(BaseModel):
    id: str
    name: str
    course: str
    vegNonveg: str
    cuisineTags: list[str] | None = None
    priceWeight: str
    isStaple: bool
    servedAsLiveStation: bool
    allergens: list[str] | None = None
    dietaryFlags: list[str] | None = None
    religionSuitability: list[str] | None = None
    occasionSuitability: list[str] | None = None
    spiceLevel: str | None = None
    prepMethod: str | None = None
    portionUnit: str | None = None
    costPerPerson: float | None = None
    taxCategoryId: str | None = None
    active: bool
    confidence: str | None = None
    sourceDocs: list[str] | None = None
    createdAt: datetime
    updatedAt: datetime

    model_config = ConfigDict(from_attributes=True)


class MenuItemCreate(BaseModel):
    name: str
    course: str
    vegNonveg: str
    priceWeight: str
    cuisineTags: list[str] | None = None
    isStaple: bool = False
    servedAsLiveStation: bool = False
    allergens: list[str] | None = None
    dietaryFlags: list[str] | None = None
    religionSuitability: list[str] | None = None
    occasionSuitability: list[str] | None = None
    spiceLevel: str | None = None
    prepMethod: str | None = None
    portionUnit: str | None = None
    costPerPerson: float | None = None
    taxCategoryId: str | None = None
    active: bool = True
    confidence: str | None = None
    sourceDocs: list[str] | None = None


class MenuItemUpdate(BaseModel):
    name: str | None = None
    course: str | None = None
    vegNonveg: str | None = None
    priceWeight: str | None = None
    cuisineTags: list[str] | None = None
    isStaple: bool | None = None
    servedAsLiveStation: bool | None = None
    allergens: list[str] | None = None
    dietaryFlags: list[str] | None = None
    religionSuitability: list[str] | None = None
    occasionSuitability: list[str] | None = None
    spiceLevel: str | None = None
    prepMethod: str | None = None
    portionUnit: str | None = None
    costPerPerson: float | None = None
    taxCategoryId: str | None = None
    active: bool | None = None
    confidence: str | None = None
    sourceDocs: list[str] | None = None
