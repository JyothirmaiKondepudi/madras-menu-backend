"""Validated configuration inputs; orgId must come from the authenticated user.

No orgId is accepted from a request payload. Full replacement inputs avoid
validating partial guest/date ranges independently of the stored record.
"""
from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from models.choices import Diet, EventType, ServiceStyle


class PricingInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=100)
    active: bool = True


class PricingTierCreate(PricingInput):
    position: int = Field(ge=0)
    isBase: bool = False
    description: str | None = None


class ConditionalPriceInput(PricingInput):
    eventType: EventType | None = None
    serviceStyle: ServiceStyle | None = None
    diet: Diet | None = None
    minGuests: int = Field(default=1, gt=0)
    maxGuests: int | None = Field(default=None, gt=0)
    effectiveFrom: date
    effectiveUntil: date | None = None
    currency: str = Field(pattern=r"^[A-Z]{3}$")

    @model_validator(mode="after")
    def valid_ranges(self):
        if self.maxGuests is not None and self.maxGuests < self.minGuests:
            raise ValueError("maxGuests must be at least minGuests")
        if self.effectiveUntil is not None and self.effectiveUntil <= self.effectiveFrom:
            raise ValueError("effectiveUntil must be after effectiveFrom (exclusive end)")
        return self


class PricingBaseRateCreate(ConditionalPriceInput):
    pricePerPerson: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    minimumCharge: Decimal = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=2)
    inclusions: str = Field(min_length=1)


class PricingAdjustmentCreate(ConditionalPriceInput):
    tierId: UUID | None = None
    menuItemId: UUID | None = None
    amount: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    chargeUnit: Literal["guest", "event"]


class PricingTierAdditionCreate(ConditionalPriceInput):
    tierId: UUID
    description: str = Field(min_length=1)
    amount: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    chargeUnit: Literal["guest", "event"]
