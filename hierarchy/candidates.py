"""
Candidate-parent retrieval for the automated (embedding-driven) classify
stage — see docs/ETL_PIPELINE.md "Version 2". Replaces prompt.py's
"send the LLM the entire catalog" approach (fine for the original 79-item
seed set, not for 1,455 real dishes: too many tokens, and it forces the
model to reason over hundreds of irrelevant dishes per proposal).

Every menu item already has a stored embedding (embeddings/backfill.py) —
this reuses that vector directly as the similarity query instead of paying
for a second Ollama embedding call per item.
"""

from sqlalchemy import text
from sqlalchemy.orm import Session


def find_candidate_parents(db: Session, item_id: str, k: int = 8) -> list[dict]:
    """Top-k dishes (by cosine distance) closest to item_id's own embedding,
    excluding item_id itself. Returns id/name/course/cuisine_tags/is_staple
    plus its current parent_id in the tree (if any) — genuinely useful
    context for the model (e.g. seeing that "Basmati rice" is already a
    root with several children makes it a more obviously correct parent
    than a candidate that's an isolated leaf)."""
    rows = db.execute(
        text(
            """
            SELECT
                m.id, m.name, m.course, m.cuisine_tags, m.is_staple,
                r.to_item_id AS current_parent_id
            FROM menu_item_embeddings e
            JOIN menu_items m ON m.id = e.item_id
            LEFT JOIN item_relationships r
                ON r.from_item_id = m.id AND r.relationship_type = 'parent_of'
            WHERE e.item_id != :item_id
            ORDER BY e.embedding <=> (
                SELECT embedding FROM menu_item_embeddings WHERE item_id = :item_id
            )
            LIMIT :k
            """
        ),
        {"item_id": item_id, "k": k},
    ).mappings().all()
    return [dict(row) for row in rows]
