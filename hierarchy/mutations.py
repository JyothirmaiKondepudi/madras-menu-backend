"""Changes to the dish hierarchy: parent_of edges between menu items.

Every change runs in the caller's session and transaction (the route commits),
and first takes a transaction-scoped advisory lock on the hierarchy. Without
it, two requests could each pass the loop check before the other saved
(A under B, and B under A, at the same moment) and together create a loop.
With it, the second waits for the first to commit and then checks against the
saved tree. Hierarchy edits are rare, so waiting costs nothing noticeable.
"""

from uuid import UUID

from sqlalchemy import delete, exists, select, text, update
from sqlalchemy.orm import Session

from models import ItemRelationship, MenuItem

# The only relationship type so far. The database also restricts it (a CHECK
# constraint), and the one-parent-per-child index only covers this type.
RELATIONSHIP_TYPES = ("parent_of",)


class HierarchyError(Exception):
    """Raised when a change would break the tree's rules."""


def _lock_hierarchy(db: Session) -> None:
    """Serializes hierarchy changes until this transaction ends."""
    db.execute(text("SELECT pg_advisory_xact_lock(hashtext('item_relationships'))"))


def _check_type(relationship_type: str) -> None:
    if relationship_type not in RELATIONSHIP_TYPES:
        raise HierarchyError(f"unknown relationship type {relationship_type!r}")


def _item_exists(db: Session, item_id: UUID) -> bool:
    return db.scalar(select(exists().where(MenuItem.id == item_id)))


def _edge(db: Session, child_id: UUID, relationship_type: str) -> ItemRelationship | None:
    return db.scalars(
        select(ItemRelationship).where(
            ItemRelationship.fromItemId == child_id,
            ItemRelationship.relationshipType == relationship_type,
        )
    ).first()


def _is_ancestor(db: Session, candidate: UUID, of_item: UUID, relationship_type: str) -> bool:
    """True if `candidate` is somewhere above `of_item` in the tree. One
    recursive query rather than one query per level; UNION (not UNION ALL)
    drops repeats, so it stops even if the data already holds a loop."""
    ancestors = (
        select(ItemRelationship.toItemId.label("item_id"))
        .where(
            ItemRelationship.fromItemId == of_item,
            ItemRelationship.relationshipType == relationship_type,
        )
        .cte("ancestors", recursive=True)
    )
    ancestors = ancestors.union(
        select(ItemRelationship.toItemId).where(
            ItemRelationship.fromItemId == ancestors.c.item_id,
            ItemRelationship.relationshipType == relationship_type,
        )
    )
    return db.scalar(select(exists().where(ancestors.c.item_id == candidate)))


def _validate_link(db: Session, child_id: UUID, parent_id: UUID, relationship_type: str) -> None:
    _check_type(relationship_type)
    if not _item_exists(db, child_id):
        raise HierarchyError(f"child_id {child_id} does not exist in menu_items")
    if not _item_exists(db, parent_id):
        raise HierarchyError(f"parent_id {parent_id} does not exist in menu_items")
    if child_id == parent_id:
        raise HierarchyError("an item cannot be its own parent")
    # the child's own edge doesn't matter here: linking makes a loop only if
    # the child is already above the new parent
    if _is_ancestor(db, child_id, parent_id, relationship_type):
        raise HierarchyError(f"linking {child_id} -> {parent_id} would create a cycle")


def _metadata(confidence: str | None, reason: str | None) -> dict | None:
    if confidence is None and reason is None:
        return None
    return {"confidence": confidence, "reason": reason}


def insert_edge(
    db: Session,
    child_id: UUID,
    parent_id: UUID,
    relationship_type: str = "parent_of",
    confidence: str | None = None,
    reason: str | None = None,
) -> ItemRelationship:
    """Add a new edge. Raises HierarchyError if child/parent don't exist, the
    child would be its own parent, this would create a cycle, or the child
    already has an edge of this type (use update_edge to change it)."""
    _lock_hierarchy(db)
    _validate_link(db, child_id, parent_id, relationship_type)
    if _edge(db, child_id, relationship_type) is not None:
        raise HierarchyError(
            f"{child_id} already has a {relationship_type!r} edge — use update_edge to change it, not insert_edge"
        )
    edge = ItemRelationship(
        fromItemId=child_id,
        toItemId=parent_id,
        relationshipType=relationship_type,
        relationshipMetadata=_metadata(confidence, reason),
    )
    db.add(edge)
    db.flush()
    return edge


def update_edge(
    db: Session,
    child_id: UUID,
    new_parent_id: UUID,
    relationship_type: str = "parent_of",
    confidence: str | None = None,
    reason: str | None = None,
) -> ItemRelationship:
    """Reclassify: point child_id at new_parent_id instead, whether or not it
    already had a parent. The edge keeps its id when it already existed."""
    _lock_hierarchy(db)
    _validate_link(db, child_id, new_parent_id, relationship_type)
    edge = _edge(db, child_id, relationship_type)
    if edge is None:
        edge = ItemRelationship(fromItemId=child_id, relationshipType=relationship_type)
        db.add(edge)
    edge.toItemId = new_parent_id
    edge.relationshipMetadata = _metadata(confidence, reason)
    db.flush()
    return edge


def delete_edge(db: Session, child_id: UUID, relationship_type: str = "parent_of") -> bool:
    """Remove child_id's edge, making it a root again. True if one was removed."""
    _check_type(relationship_type)
    _lock_hierarchy(db)
    result = db.execute(
        delete(ItemRelationship).where(
            ItemRelationship.fromItemId == child_id,
            ItemRelationship.relationshipType == relationship_type,
        )
    )
    return result.rowcount > 0


def delete_node(db: Session, item_id: UUID, relationship_type: str = "parent_of") -> dict:
    """Remove item_id from the tree: its children move up to its own parent
    (or become roots if it had none) instead of being deleted or orphaned.
    Relies on edges meaning "is a more specific variant of": skipping the
    removed dish one level is still accurate for that relationship. No loop
    check is needed, since moving a child to its grandparent can't make one.

    Does not delete the menu_items row itself, only its place in the tree.

    Returns {"parent_id": <id or None>, "reparented_children": [<ids>]}.
    """
    _check_type(relationship_type)
    _lock_hierarchy(db)
    own_edge = _edge(db, item_id, relationship_type)
    parent_id = own_edge.toItemId if own_edge is not None else None
    child_ids = list(
        db.scalars(
            select(ItemRelationship.fromItemId).where(
                ItemRelationship.toItemId == item_id,
                ItemRelationship.relationshipType == relationship_type,
            )
        )
    )

    if own_edge is not None:
        db.delete(own_edge)
    children = (ItemRelationship.toItemId == item_id) & (
        ItemRelationship.relationshipType == relationship_type
    )
    if parent_id is not None:
        db.execute(
            update(ItemRelationship)
            .where(children)
            .values(
                toItemId=parent_id,
                relationshipMetadata=_metadata(
                    None,
                    "reparented one level up after its direct parent was deleted from the tree",
                ),
            )
        )
    else:
        # the removed dish was a root, so its children become roots
        db.execute(delete(ItemRelationship).where(children))
    db.flush()
    # the bulk statements bypassed any copies of these rows already loaded
    db.expire_all()
    return {"parent_id": parent_id, "reparented_children": child_ids}
