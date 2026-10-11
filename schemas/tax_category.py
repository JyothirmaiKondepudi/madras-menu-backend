from pydantic import BaseModel, ConfigDict, Field
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


class TaxCategoryCreate(BaseModel):
    name: str
    jurisdiction: str
    ratePercent: Decimal = Field(ge=0, max_digits=5, decimal_places=3)


class TaxCategoryUpdate(BaseModel):
    name: str | None = None
    jurisdiction: str | None = None
    ratePercent: Decimal = Field(ge=0, max_digits=5, decimal_places=3)
