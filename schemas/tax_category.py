from pydantic import BaseModel, ConfigDict, Field, field_serializer
from datetime import datetime
from uuid import UUID
from decimal import Decimal


class TaxCategoryOut(BaseModel):
    id: UUID
    name: str
    jurisdiction: str
    ratePercent: Decimal
    effectiveDate: datetime

    model_config = ConfigDict(from_attributes=True)

    # Decimal inside the app, a plain JSON number on the way out: the
    # frontend only displays these, it never does arithmetic on them
    @field_serializer("ratePercent", when_used="json")
    def _decimal_as_number(self, value: Decimal | None) -> float | None:
        return None if value is None else float(value)


class TaxCategoryCreate(BaseModel):
    name: str
    jurisdiction: str
    ratePercent: Decimal = Field(ge=0, max_digits=5, decimal_places=3)


class TaxCategoryUpdate(BaseModel):
    name: str | None = None
    jurisdiction: str | None = None
    ratePercent: Decimal = Field(default=None, ge=0, max_digits=5, decimal_places=3)
