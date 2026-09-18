from sqlalchemy import Column, String, DateTime, ForeignKey, func
from pgvector.sqlalchemy import Vector
from database import Base

# Brand-new table, owned entirely by this app (in Alembic's OWNED_TABLES,
# see alembic/env.py) — never touches menu_items itself, only references
# it. See docs/ETL_PIPELINE.md for the full design: this is pure
# *retrieval* (semantic search for candidate parents), never a second
# place the tree's actual parent/child structure lives — that stays
# exclusively in item_relationships. See the README's "makes sense"
# discussion for why a parent_id column here was deliberately rejected.


class MenuItemEmbedding(Base):
    __tablename__ = 'menu_item_embeddings'

    # One embedding per dish — item_id IS the primary key (no separate
    # surrogate id needed), which also makes "regenerate this dish's
    # embedding" a plain upsert on a known key, not a lookup-then-update.
    itemId = Column("item_id", String, ForeignKey('menu_items.id'), primary_key=True)

    # 768 dims to match Ollama's nomic-embed-text. If a different
    # embedding model is used later, this dimension has to change too —
    # a mismatch fails loudly on insert, not silently.
    embedding = Column("embedding", Vector(768), nullable=False)

    # The exact text that was embedded (name + course + cuisine_tags,
    # per docs/ETL_PIPELINE.md) — kept for debugging/audit, so a bad
    # search result can be traced back to what was actually embedded.
    embeddedText = Column("embedded_text", String, nullable=False)

    createdAt = Column("created_at", DateTime, server_default=func.now(), nullable=False)
