from pydantic import BaseModel, ConfigDict

class ItemRelationshipOut(BaseModel):
    id: str
    fromItemId: str
    toItemId: str
    relationshipType: str
    relationshipMetadata: dict | None = None

    model_config = ConfigDict(from_attributes=True)


class ItemRelationshipCreate(BaseModel):
    childId: str
    parentId: str
    relationshipType: str = "parent_of"
    confidence: str | None = None
    reason: str | None = None


class ItemRelationshipUpdate(BaseModel):
    newParentId: str
    relationshipType: str = "parent_of"
    confidence: str | None = None
    reason: str | None = None
