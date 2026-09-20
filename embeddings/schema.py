from datetime import datetime
from pydantic import BaseModel, ConfigDict


class EmbeddingOut(BaseModel):
    itemId: str
    embeddedText: str
    createdAt: datetime

    model_config = ConfigDict(from_attributes=True)


class SearchResult(BaseModel):
    itemId: str
    name: str
    distance: float
