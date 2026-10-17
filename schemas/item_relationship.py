from pydantic import BaseModel, ConfigDict
from uuid import UUID


class ItemRelationshipOut(BaseModel):
    id: UUID
    fromItemId: UUID
    toItemId: UUID
    relationshipType: str
    relationshipMetadata: dict | None = None

    model_config = ConfigDict(from_attributes=True)


class ItemRelationshipCreate(BaseModel):
    childId: UUID
    parentId: UUID
    relationshipType: str = "parent_of"
    confidence: str | None = None
    reason: str | None = None


class ItemRelationshipUpdate(BaseModel):
    newParentId: UUID
    relationshipType: str = "parent_of"
    confidence: str | None = None
    reason: str | None = None
