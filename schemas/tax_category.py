from pydantic import BaseModel, ConfigDict
from datetime import datetime

class TaxCategoryOut(BaseModel):
    id: str
    name: str
    jurisdiction: str
    ratePercent: float
    effectiveDate: datetime

    model_config = ConfigDict(from_attributes=True)


class TaxCategoryCreate(BaseModel):
    name: str
    jurisdiction: str
    ratePercent: float


class TaxCategoryUpdate(BaseModel):
    name: str | None = None
    jurisdiction: str | None = None
    ratePercent: float | None = None
