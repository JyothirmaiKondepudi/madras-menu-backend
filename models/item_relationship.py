from sqlalchemy import Column, String, DateTime, Index, ForeignKey, text, func
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

    id = Column("id", String, primary_key=True, default=lambda: str(uuid.uuid4()))
    fromItemId = Column(
        "from_item_id",
        String,
        ForeignKey("menu_items.id", onupdate="CASCADE", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    toItemId = Column(
        "to_item_id",
        String,
        ForeignKey("menu_items.id", onupdate="CASCADE", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    relationshipType = Column("relationship_type", String, nullable=False)
    relationshipMetadata = Column("metadata", JSONB)
    createdAt = Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False)
