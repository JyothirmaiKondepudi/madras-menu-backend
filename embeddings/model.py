from sqlalchemy import Column, String, DateTime, ForeignKey, Index, func, UUID
from pgvector.sqlalchemy import Vector
from database import Base

# Retrieval only (semantic search for candidate parents). The parent/child
# tree lives solely in item_relationships. See docs/ETL_PIPELINE.md.


class MenuItemEmbedding(Base):
    __tablename__ = "menu_item_embeddings"
    __table_args__ = (
        # HNSW over IVFFlat: works on an empty table; IVFFlat needs existing data.
        # Ops class must match the query's `<=>` (cosine) or the index is skipped.
        Index(
            "menu_item_embeddings_hnsw_cosine",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    # One embedding per dish; item_id as PK makes regeneration a plain upsert.
    itemId = Column(
        "item_id", UUID(as_uuid=True), ForeignKey("menu_items.id"), primary_key=True
    )

    # 768 dims for Ollama's nomic-embed-text; change if the model changes.
    embedding = Column("embedding", Vector(768), nullable=False)

    # Source text (name + course + cuisine_tags), kept for debugging bad matches.
    embeddedText = Column("embedded_text", String, nullable=False)

    createdAt = Column(
        "created_at", DateTime(timezone=True), server_default=func.now(), nullable=False
    )
