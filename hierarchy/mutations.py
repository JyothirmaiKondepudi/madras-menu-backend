"""CRUD for parent_of edges in the hierarchy tree. Operates directly on the database (psycopg2), not a proposals file."""

from uuid import UUID


class HierarchyError(Exception):
    """Raised when a mutation would violate the tree's rules."""


def _item_exists(cur, item_id: UUID) -> bool:
    cur.execute("SELECT 1 FROM menu_items WHERE id = %s", (item_id,))
    return cur.fetchone() is not None


def _existing_parent(
    cur, child_id: UUID, relationship_type: str = "parent_of"
) -> UUID | None:
    cur.execute(
        "SELECT to_item_id FROM item_relationships WHERE from_item_id = %s AND relationship_type = %s",
        (child_id, relationship_type),
    )
    row = cur.fetchone()
    return row[0] if row else None


def _would_create_cycle(
    cur, child_id: UUID, new_parent_id: UUID, relationship_type: str = "parent_of"
) -> bool:
    """True if child_id appears in new_parent_id's ancestor chain (i.e. this edge would create a cycle)."""
    current = new_parent_id
    seen = set()
    for _ in range(10_000):
        if current == child_id:
            return True
        if current in seen:
            return False
        seen.add(current)
        current = _existing_parent(cur, current, relationship_type)
        if current is None:
            return False
    return True


def insert_edge(
    cur,
    child_id: UUID,
    parent_id: UUID,
    relationship_type: str = "parent_of",
    confidence: str | None = None,
    reason: str | None = None,
) -> UUID:
    """Add a new edge. Raises HierarchyError if child/parent don't exist, child would be
    its own parent, this would create a cycle, or child already has an edge of this type
    (use update_edge instead). Returns the new edge's id."""
    if not _item_exists(cur, child_id):
        raise HierarchyError(f"child_id {child_id} does not exist in menu_items")
    if not _item_exists(cur, parent_id):
        raise HierarchyError(f"parent_id {parent_id} does not exist in menu_items")
    if child_id == parent_id:
        raise HierarchyError("an item cannot be its own parent")
    if _existing_parent(cur, child_id, relationship_type) is not None:
        raise HierarchyError(
            f"{child_id} already has a {relationship_type!r} edge — use update_edge to change it, not insert_edge"
        )
    if _would_create_cycle(cur, child_id, parent_id, relationship_type):
        raise HierarchyError(f"linking {child_id} -> {parent_id} would create a cycle")

    cur.execute(
        """
        INSERT INTO item_relationships (id, from_item_id, to_item_id, relationship_type, metadata)
        VALUES (gen_random_uuid(), %s, %s, %s, %s)
        RETURNING id
        """,
        (child_id, parent_id, relationship_type, _metadata_json(confidence, reason)),
    )
    return cur.fetchone()[0]


def update_edge(
    cur,
    child_id: UUID,
    new_parent_id: UUID,
    relationship_type: str = "parent_of",
    confidence: str | None = None,
    reason: str | None = None,
) -> UUID:
    """Reclassify: point child_id's edge at new_parent_id instead, whether or not
    it already had one. Returns the edge's id."""
    if not _item_exists(cur, child_id):
        raise HierarchyError(f"child_id {child_id} does not exist in menu_items")
    if not _item_exists(cur, new_parent_id):
        raise HierarchyError(
            f"new_parent_id {new_parent_id} does not exist in menu_items"
        )
    if child_id == new_parent_id:
        raise HierarchyError("an item cannot be its own parent")

    # Remove the old edge first so the cycle check doesn't flag itself
    cur.execute(
        "DELETE FROM item_relationships WHERE from_item_id = %s AND relationship_type = %s",
        (child_id, relationship_type),
    )
    if _would_create_cycle(cur, child_id, new_parent_id, relationship_type):
        raise HierarchyError(
            f"linking {child_id} -> {new_parent_id} would create a cycle"
        )

    cur.execute(
        """
        INSERT INTO item_relationships (id, from_item_id, to_item_id, relationship_type, metadata)
        VALUES (gen_random_uuid(), %s, %s, %s, %s)
        RETURNING id
        """,
        (
            child_id,
            new_parent_id,
            relationship_type,
            _metadata_json(confidence, reason),
        ),
    )
    return cur.fetchone()[0]


def delete_node(cur, item_id: UUID, relationship_type: str = "parent_of") -> dict:
    """Remove item_id from the tree: reparents its children to its own parent
    (the grandparent) instead of cascading a delete or leaving them orphaned.
    Relies on edges meaning "is a more specific variant of" — skipping the
    deleted node one level is still accurate for that relationship.

    Does not delete the menu_items row itself, only its place in the hierarchy.

    Returns {"parent_id": <id or None>, "reparented_children": [<ids>]}.
    """
    parent_id = _existing_parent(cur, item_id, relationship_type)
    cur.execute(
        "SELECT from_item_id FROM item_relationships WHERE to_item_id = %s AND relationship_type = %s",
        (item_id, relationship_type),
    )
    child_ids = [row[0] for row in cur.fetchall()]

    cur.execute(
        "DELETE FROM item_relationships WHERE from_item_id = %s AND relationship_type = %s",
        (item_id, relationship_type),
    )

    reparented = []
    if parent_id is not None:
        for child_id in child_ids:
            update_edge(
                cur,
                child_id,
                parent_id,
                relationship_type,
                reason="reparented one level up after its direct parent was deleted from the tree",
            )
            reparented.append(child_id)
    # deleted node was a root — its children become new roots
    else:
        for child_id in child_ids:
            delete_edge(cur, child_id, relationship_type)
            reparented.append(child_id)

    return {"parent_id": parent_id, "reparented_children": reparented}


def delete_edge(cur, child_id: UUID, relationship_type: str = "parent_of") -> bool:
    """Remove child_id's edge, making it a root again. Returns True if a row was deleted."""
    cur.execute(
        "DELETE FROM item_relationships WHERE from_item_id = %s AND relationship_type = %s",
        (child_id, relationship_type),
    )
    return cur.rowcount > 0


def _metadata_json(confidence: str | None, reason: str | None) -> str | None:
    import json

    if confidence is None and reason is None:
        return None
    return json.dumps({"confidence": confidence, "reason": reason})
