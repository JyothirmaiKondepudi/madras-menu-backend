from sqlalchemy import Column, String, DateTime, Index, ForeignKey, text, func, UUID
from sqlalchemy.dialects.postgresql import JSONB
import uuid
from database import Base


class ItemRelationship(Base):
    __tablename__ = "item_relationships"
    __table_args__ = (
        Index(
            "item_relationships_one_parent_per_child",
            "from_item_id",
            unique=True,
            postgresql_where=text("relationship_type = 'parent_of'"),
        ),
    )

    id = Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fromItemId = Column(
        "from_item_id",
        UUID(as_uuid=True),
        ForeignKey("menu_items.id", onupdate="CASCADE", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    toItemId = Column(
        "to_item_id",
        UUID(as_uuid=True),
        ForeignKey("menu_items.id", onupdate="CASCADE", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    relationshipType = Column("relationship_type", String, nullable=False)
    relationshipMetadata = Column("metadata", JSONB)
    createdAt = Column(
        "created_at", DateTime(timezone=True), server_default=func.now(), nullable=False
    )
