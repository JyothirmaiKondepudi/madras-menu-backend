"""Validated configuration inputs; orgId must come from the authenticated user.

No orgId is accepted from a request payload. Full replacement inputs avoid
validating partial guest/date ranges independently of the stored record.
"""
from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from models.choices import (
    Diet, EventType, LiveStationDiet, PriceWeight, PricingMethod, ServiceStyle, TaxMode,
)


class PricingInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=100)
    active: bool = True


class PricingModelCreate(PricingInput):
    """A new draft pricing version. The version number and status are set by
    the server; `active` doesn't apply to models (status does)."""
    method: PricingMethod = PricingMethod.TIERED_PER_GUEST
    notes: str | None = None


class PricingTierCreate(PricingInput):
    position: int = Field(ge=0)
    isBase: bool = False
    description: str | None = None


class PricingTierCourseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    tierId: UUID
    course: str = Field(min_length=1, max_length=50)
    dishCount: int = Field(gt=0)
    # dish classes the tier's base price covers; any other class is a surcharge
    includedPriceWeights: list[PriceWeight] = Field(default_factory=list)
    position: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def unique_weights(self):
        if len(set(self.includedPriceWeights)) != len(self.includedPriceWeights):
            raise ValueError("includedPriceWeights lists a class twice")
        return self


def _percent():
    return Field(default=Decimal("0"), ge=0, le=100, max_digits=5, decimal_places=2)


class PricingPolicyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    serviceChargePercent: Decimal = _percent()
    gratuityPercent: Decimal = _percent()
    taxMode: TaxMode = TaxMode.PER_DISH_CATEGORY
    flatTaxPercent: Decimal | None = Field(default=None, ge=0, le=100, max_digits=6, decimal_places=3)
    roundingIncrement: Decimal = Field(default=Decimal("0.01"), gt=0, max_digits=8, decimal_places=2)
    depositPercent: Decimal = _percent()
    quoteValidDays: int = Field(default=30, gt=0)

    @model_validator(mode="after")
    def flat_tax_matches_mode(self):
        if (self.taxMode == TaxMode.FLAT_RATE) != (self.flatTaxPercent is not None):
            raise ValueError("flatTaxPercent is required with taxMode flat_rate, and only then")
        return self


class LiveStationCreate(BaseModel):
    """A caterer's live station; the organization comes from the caller."""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=200)
    region: str = Field(min_length=1, max_length=100)
    vegNonveg: LiveStationDiet
    description: str | None = None
    pricePerPerson: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    minGuests: int = Field(default=1, gt=0)
    equipmentNeeded: list[str] = Field(default_factory=list)
    active: bool = True


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
    priceWeight: PriceWeight | None = None
    amount: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    chargeUnit: Literal["guest", "event"]

    @model_validator(mode="after")
    def dish_or_class(self):
        if self.menuItemId is not None and self.priceWeight is not None:
            raise ValueError("give menuItemId or priceWeight, not both")
        return self


class PricingTierAdditionCreate(ConditionalPriceInput):
    tierId: UUID
    description: str = Field(min_length=1)
    amount: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    chargeUnit: Literal["guest", "event"]
