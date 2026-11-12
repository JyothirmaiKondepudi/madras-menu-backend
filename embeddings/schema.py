from datetime import datetime
from pydantic import BaseModel, ConfigDict
from uuid import UUID


class EmbeddingOut(BaseModel):
    itemId: UUID
    embeddedText: str
    createdAt: datetime

    model_config = ConfigDict(from_attributes=True)


class SearchResult(BaseModel):
    itemId: UUID
    name: str
    distance: float
