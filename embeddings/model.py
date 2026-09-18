from sqlalchemy import Column, String, DateTime, ForeignKey, Index, func
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
    __table_args__ = (
        # HNSW, not IVFFlat: HNSW builds incrementally as rows are inserted
        # (fine to create on an empty table, which this is right now) —
        # IVFFlat instead needs a representative sample of real vectors
        # already present to cluster well, which doesn't exist yet.
        # vector_cosine_ops matches the `<=>` operator the search query
        # actually uses (cosine distance) — an index built with the wrong
        # ops class silently isn't used by a query using a different one.
        Index(
            'menu_item_embeddings_hnsw_cosine',
            'embedding',
            postgresql_using='hnsw',
            postgresql_ops={'embedding': 'vector_cosine_ops'},
        ),
    )

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
