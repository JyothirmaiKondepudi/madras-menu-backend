from sqlalchemy import CheckConstraint, Column, String, DateTime, Index, ForeignKeyConstraint, text, func, UUID
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
        # backstops for the rules in hierarchy/mutations.py
        CheckConstraint(
            "from_item_id <> to_item_id", name="item_relationships_not_own_parent_check"
        ),
        ForeignKeyConstraint(
            ["org_id", "from_item_id"], ["menu_items.org_id", "menu_items.id"],
            name="item_relationships_from_item_org_fkey", onupdate="CASCADE", ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["org_id", "to_item_id"], ["menu_items.org_id", "menu_items.id"],
            name="item_relationships_to_item_org_fkey", onupdate="CASCADE", ondelete="RESTRICT",
        ),
        CheckConstraint(
            "relationship_type IN ('parent_of')",
            name="item_relationships_relationship_type_check",
        ),
    )

    id = Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # the caterer both dishes belong to; the composite foreign keys below
    # make a link between two caterers' dishes impossible
    orgId = Column("org_id", UUID(as_uuid=True), nullable=False, index=True)
    fromItemId = Column("from_item_id", UUID(as_uuid=True), nullable=False, index=True)
    toItemId = Column("to_item_id", UUID(as_uuid=True), nullable=False, index=True)
    relationshipType = Column("relationship_type", String, nullable=False)
    relationshipMetadata = Column("metadata", JSONB)
    createdAt = Column(
        "created_at", DateTime(timezone=True), server_default=func.now(), nullable=False
    )
