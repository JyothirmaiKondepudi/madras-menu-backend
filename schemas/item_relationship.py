from typing import Literal

from pydantic import BaseModel, ConfigDict
from uuid import UUID

# the only type so far; see hierarchy/mutations.py
RelationshipType = Literal["parent_of"]


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
    relationshipType: RelationshipType = "parent_of"
    confidence: str | None = None
    reason: str | None = None


class ItemRelationshipUpdate(BaseModel):
    newParentId: UUID
    relationshipType: RelationshipType = "parent_of"
    confidence: str | None = None
    reason: str | None = None
