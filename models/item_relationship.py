from sqlalchemy import Column, String, DateTime, Index, ForeignKey, text, func
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime
import uuid
from database import Base


class ItemRelationship(Base):
    __tablename__ = 'item_relationships'
    __table_args__ = (
        Index(
            'item_relationships_one_parent_per_child',
            'from_item_id',
            unique=True,
            postgresql_where=text("relationship_type = 'parent_of'"),
        ),
    )

    id = Column("id", String, primary_key=True, default=lambda: str(uuid.uuid4()))
    fromItemId = Column("from_item_id", String, ForeignKey('menu_items.id'), nullable=False)
    toItemId = Column("to_item_id", String, ForeignKey('menu_items.id'), nullable=False)
    relationshipType = Column("relationship_type", String, nullable=False)
    relationshipMetadata = Column("metadata", JSONB)
    createdAt = Column("created_at", DateTime, default=datetime.now, server_default=func.now(), nullable=False)
