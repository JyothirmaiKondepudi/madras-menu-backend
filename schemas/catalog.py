from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from models.choices import PricingUnit

Money = Field(ge=0, max_digits=12, decimal_places=2)
Hours = Field(gt=0, max_digits=5, decimal_places=2)


class RateCardItemOut(BaseModel):
    id: UUID
    name: str
    price: Decimal
    pricingUnit: PricingUnit
    hours: Decimal | None = None
    category: str | None = None
    active: bool
    createdAt: datetime
    updatedAt: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("price", "hours", when_used="json")
    def _decimal_as_number(self, value: Decimal | None) -> float | None:
        return None if value is None else float(value)


class RateCardItemCreate(BaseModel):
    name: str = Field(min_length=1)
    price: Decimal = Money
    pricingUnit: PricingUnit
    hours: Decimal | None = Field(default=None, gt=0, max_digits=5, decimal_places=2)
    category: str | None = None
    active: bool = True


class RateCardItemUpdate(BaseModel):
    # leaving a field out keeps it; the required ones can't be set to null
    # (typed without None, so an explicit null is a 422)
    name: str = Field(default=None, min_length=1)
    price: Decimal = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    pricingUnit: PricingUnit = None
    hours: Decimal | None = Field(default=None, gt=0, max_digits=5, decimal_places=2)
    category: str | None = None
    active: bool = None


class EquipmentOut(BaseModel):
    id: UUID
    name: str
    amount: Decimal
    active: bool
    createdAt: datetime
    updatedAt: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("amount", when_used="json")
    def _decimal_as_number(self, value: Decimal) -> float:
        return float(value)


class EquipmentCreate(BaseModel):
    name: str = Field(min_length=1)
    amount: Decimal = Money
    active: bool = True


class EquipmentUpdate(BaseModel):
    name: str = Field(default=None, min_length=1)
    amount: Decimal = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    active: bool = None
