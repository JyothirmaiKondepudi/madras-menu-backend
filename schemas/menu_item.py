from pydantic import BaseModel, ConfigDict, Field, field_serializer
from decimal import Decimal
from datetime import datetime
from uuid import UUID


class MenuItemOut(BaseModel):
    id: UUID
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
    costPerPerson: Decimal | None
    taxCategoryId: UUID | None = None
    active: bool
    confidence: str | None = None
    sourceDocs: list[str] | None = None
    createdAt: datetime
    updatedAt: datetime

    model_config = ConfigDict(from_attributes=True)

    # Decimal inside the app, a plain JSON number on the way out: the
    # frontend only displays these, it never does arithmetic on them
    @field_serializer("costPerPerson", when_used="json")
    def _decimal_as_number(self, value: Decimal | None) -> float | None:
        return None if value is None else float(value)


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
    costPerPerson: Decimal | None = Field(
        default=None, ge=0, max_digits=8, decimal_places=2
    )
    taxCategoryId: UUID | None = None
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
    costPerPerson: Decimal | None = Field(
        default=None, ge=0, max_digits=8, decimal_places=2
    )
    taxCategoryId: UUID | None = None
    active: bool | None = None
    confidence: str | None = None
    sourceDocs: list[str] | None = None
