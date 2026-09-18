import os

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session
from langchain_ollama import OllamaEmbeddings

from models import MenuItem
from embeddings.model import MenuItemEmbedding

# Configurable, not hardcoded to "my laptop" — Ollama's own default local port.
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
EMBEDDING_MODEL = "nomic-embed-text"

_embeddings_client = OllamaEmbeddings(model=EMBEDDING_MODEL, base_url=OLLAMA_BASE_URL)


def build_embedding_text(name: str, course: str, cuisine_tags: list[str] | None) -> str:
    """name + course + cuisine_tags, per docs/ETL_PIPELINE.md — a bare name
    alone is often too ambiguous (e.g. "Pilaf" says nothing about it being
    a rice dish); course and cuisine tags give the embedding model real
    disambiguating signal, directly relevant to matching regional name
    variants (Pulihora / Puliogare / Tamarind rice) to the right dish."""
    tags = ", ".join(cuisine_tags or [])
    return f"{name} ({course}, {tags})" if tags else f"{name} ({course})"


def generate_embedding(text: str) -> list[float]:
    return _embeddings_client.embed_query(text)


def upsert_embedding(db: Session, item_id: str, embedding: list[float], embedded_text: str) -> MenuItemEmbedding:
    """Insert or replace — regenerating an existing dish's embedding (its
    name/tags changed, or it's just being re-run) updates the row rather
    than failing on the primary key."""
    stmt = pg_insert(MenuItemEmbedding).values(
        item_id=item_id, embedding=embedding, embedded_text=embedded_text
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["item_id"],
        set_={"embedding": stmt.excluded.embedding, "embedded_text": stmt.excluded.embedded_text},
    )
    db.execute(stmt)
    db.commit()
    return db.get(MenuItemEmbedding, item_id)


def embed_menu_item(db: Session, item_id: str) -> MenuItemEmbedding | None:
    """Returns None if item_id doesn't exist — the route turns that into a
    404, same pattern as every other single-item route in this app."""
    item = db.get(MenuItem, item_id)
    if item is None:
        return None
    text = build_embedding_text(item.name, item.course, item.cuisineTags)
    vector = generate_embedding(text)
    return upsert_embedding(db, item_id, vector, text)


def search_similar(db: Session, query_text: str, limit: int = 5) -> list[dict]:
    """Semantic search: embed query_text the same way dishes were embedded,
    return the top-K closest existing dishes by cosine distance — the
    retrieval step that finds e.g. the real "Tamarind rice" row for a query
    like "Tamarind infused rice with roasted peanuts and cashews"."""
    query_vector = generate_embedding(query_text)
    rows = db.execute(
        select(
            MenuItemEmbedding.itemId,
            MenuItem.name,
            MenuItemEmbedding.embedding.cosine_distance(query_vector).label("distance"),
        )
        .join(MenuItem, MenuItem.id == MenuItemEmbedding.itemId)
        .order_by(MenuItemEmbedding.embedding.cosine_distance(query_vector))
        .limit(limit)
    ).all()
    return [{"itemId": r.itemId, "name": r.name, "distance": r.distance} for r in rows]
