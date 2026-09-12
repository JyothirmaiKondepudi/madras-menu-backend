"""
Real, reusable CRUD for the tree — insert / update / delete a single
parent_of edge, each going through the same validation every time instead
of a fresh ad-hoc script per batch (which is what every batch so far
actually did, and how the tracking-file drift bug happened: the
diff/insert logic was hand-rolled each round instead of being one tested
function).

These operate directly against the database (psycopg2), not against a
proposals JSON file — the database is the only source of truth here,
which is also the fix for the drift bug: nothing needs a separate
"tracking file" kept in sync by hand anymore.
"""

import psycopg2


class HierarchyError(Exception):
    """Raised when a mutation would violate the tree's rules — never let
    these fall through as a raw IntegrityError from Postgres."""


def _item_exists(cur, item_id: str) -> bool:
    cur.execute("SELECT 1 FROM menu_items WHERE id = %s", (item_id,))
    return cur.fetchone() is not None


def _existing_parent(cur, child_id: str, relationship_type: str = "parent_of") -> str | None:
    cur.execute(
        "SELECT to_item_id FROM item_relationships WHERE from_item_id = %s AND relationship_type = %s",
        (child_id, relationship_type),
    )
    row = cur.fetchone()
    return row[0] if row else None


def _would_create_cycle(cur, child_id: str, new_parent_id: str, relationship_type: str = "parent_of") -> bool:
    """Walk new_parent_id's own ancestor chain — if child_id shows up
    anywhere in it, accepting this edge would create a cycle. Mirrors
    validate.py's _find_cycle, but reads the live DB instead of an
    in-memory proposals dict."""
    current = new_parent_id
    seen = set()
    for _ in range(10_000):  # generous bound; a real cycle would be caught long before this
        if current == child_id:
            return True
        if current in seen:
            return False  # a pre-existing cycle elsewhere, not one this edge creates
        seen.add(current)
        current = _existing_parent(cur, current, relationship_type)
        if current is None:
            return False  # reached a root — no cycle
    return True  # exceeded bound — treat as a cycle to be safe


def insert_edge(
    cur,
    child_id: str,
    parent_id: str,
    relationship_type: str = "parent_of",
    confidence: str | None = None,
    reason: str | None = None,
) -> str:
    """Add a NEW edge. Raises HierarchyError if child/parent don't exist,
    child would be its own parent, this would create a cycle, or the
    child already has an edge of this relationship_type (use update_edge
    for that — this is insert, not upsert, on purpose, so a caller can't
    silently overwrite an existing classification by accident).
    Returns the new edge's id."""
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
    child_id: str,
    new_parent_id: str,
    relationship_type: str = "parent_of",
    confidence: str | None = None,
    reason: str | None = None,
) -> str:
    """Reclassify: change child_id's existing edge to point at
    new_parent_id instead (this is exactly the operation every
    "Basmati Pilaf", "Bombay Sandwiches", etc. reclassification in this
    project's history actually needed — previously done by hand each
    time). Works whether or not child_id already had an edge. Returns the
    edge's id."""
    if not _item_exists(cur, child_id):
        raise HierarchyError(f"child_id {child_id} does not exist in menu_items")
    if not _item_exists(cur, new_parent_id):
        raise HierarchyError(f"new_parent_id {new_parent_id} does not exist in menu_items")
    if child_id == new_parent_id:
        raise HierarchyError("an item cannot be its own parent")

    # Temporarily remove the old edge before the cycle check, so
    # reclassifying to the same neighborhood isn't falsely rejected as a
    # cycle against itself.
    cur.execute(
        "DELETE FROM item_relationships WHERE from_item_id = %s AND relationship_type = %s",
        (child_id, relationship_type),
    )
    if _would_create_cycle(cur, child_id, new_parent_id, relationship_type):
        raise HierarchyError(f"linking {child_id} -> {new_parent_id} would create a cycle")

    cur.execute(
        """
        INSERT INTO item_relationships (id, from_item_id, to_item_id, relationship_type, metadata)
        VALUES (gen_random_uuid(), %s, %s, %s, %s)
        RETURNING id
        """,
        (child_id, new_parent_id, relationship_type, _metadata_json(confidence, reason)),
    )
    return cur.fetchone()[0]


def delete_node(cur, item_id: str, relationship_type: str = "parent_of") -> dict:
    """
    Delete an entire dish from the tree (not just one edge) — removes its
    own parent edge, if any, AND reparents every one of its children to
    ITS parent (grandparent-of-the-deleted-node), rather than cascading
    to delete the whole subtree or refusing outright.

    This is a deliberate choice, not a universal rule: it relies on our
    edges meaning "is a more specific variant of," where skipping a
    deleted intermediate dish and pointing its children one level higher
    is still a true (if less precise) statement — e.g. if `Basmati Pilaf`
    is deleted, `Basmati Peas Pilaf -> Basmati rice` is still accurate.
    That property doesn't hold for every kind of tree (a filesystem path
    or an org chart doesn't reparent this way), so don't reuse this
    function's behavior as a general pattern without re-checking that
    assumption holds for whatever the tree represents.

    Does NOT delete the menu_items row itself — this only removes it from
    the hierarchy; deleting the actual dish record is a separate concern
    the caller can layer on top of this (or not) as it sees fit.

    Returns {"parent_id": <id or None>, "reparented_children": [<ids>]}.
    """
    parent_id = _existing_parent(cur, item_id, relationship_type)
    cur.execute(
        "SELECT from_item_id FROM item_relationships WHERE to_item_id = %s AND relationship_type = %s",
        (item_id, relationship_type),
    )
    child_ids = [row[0] for row in cur.fetchall()]

    # Remove the deleted node's own edge (if it had a parent).
    cur.execute(
        "DELETE FROM item_relationships WHERE from_item_id = %s AND relationship_type = %s",
        (item_id, relationship_type),
    )

    reparented = []
    if parent_id is not None:
        # This node was itself a child — reattach its children to ITS
        # parent (the grandparent), preserving them as roots only if the
        # deleted node had no parent of its own (handled by the else
        # branch below implicitly, since update_edge only runs here).
        for child_id in child_ids:
            update_edge(
                cur, child_id, parent_id, relationship_type,
                reason=f"reparented one level up after its direct parent was deleted from the tree",
            )
            reparented.append(child_id)
    # else: the deleted node was itself a root — its children simply
    # become new roots (delete_edge below already removed any edge they
    # might have had FROM the deleted node; nothing more to do, since
    # there's no grandparent to reattach them to).
    else:
        for child_id in child_ids:
            delete_edge(cur, child_id, relationship_type)
            reparented.append(child_id)

    return {"parent_id": parent_id, "reparented_children": reparented}


def delete_edge(cur, child_id: str, relationship_type: str = "parent_of") -> bool:
    """Remove child_id's edge, making it a root again. Returns True if a
    row was actually deleted, False if it had no such edge to begin with
    (not an error — deleting something already absent is a no-op)."""
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
