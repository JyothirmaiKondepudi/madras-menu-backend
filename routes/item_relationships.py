from sqlalchemy.orm import Session
from uuid import UUID
from services.item_relationships import (
    add_new_item_relationship,
    delete_item_relationship_by_child_id,
    delete_node_from_hierarchy,
    item_relationships_query,
    get_item_relationship_by_child_id,
    update_item_relationship_by_child_id,
)
from fastapi import APIRouter, Depends, HTTPException
from models import ItemRelationship, User
from services.listing import Listing, Page, paginate
from schemas.item_relationship import (
    RelationshipType,
    ItemRelationshipOut,
    ItemRelationshipCreate,
    ItemRelationshipUpdate,
)
from database import get_db
from auth.dependencies import get_current_user, require_permission

# HierarchyError no longer needs to be caught here — main.py's global
# exception handler turns it into a 400 for every route, not just this one.

router = APIRouter()

# Internal hierarchy/tree tooling — gated by a single "hierarchy:manage"
# permission covering reads and writes alike, same as tax categories,
# not client-facing data. Each caterer has its own tree: every route works
# only on the caller's organization's dishes and links.

_manage = Depends(require_permission("hierarchy:manage"))


@router.get(
    "/item-relationships",
    response_model=Page[ItemRelationshipOut],
    dependencies=[_manage],
)
def get_item_relationships(
    listing: Listing, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    # edges have no timestamp or name, so they page in id order
    return paginate(
        db, item_relationships_query(current_user.userOrg), listing, {"id": ItemRelationship.id}, "id", ItemRelationship.id
    )


@router.get(
    "/item-relationships/{child_id}",
    response_model=ItemRelationshipOut,
    dependencies=[_manage],
)
def get_item_relationship(
    child_id: UUID,
    relationship_type: RelationshipType = "parent_of",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    edge = get_item_relationship_by_child_id(child_id, current_user.userOrg, db, relationship_type)
    if edge is None:
        raise HTTPException(status_code=404, detail="no such edge")
    return edge


@router.post(
    "/item-relationships", response_model=ItemRelationshipOut, dependencies=[_manage]
)
def add_item_relationship(
    new_edge: ItemRelationshipCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    created_edge = add_new_item_relationship(new_edge, current_user.userOrg, db)
    db.commit()
    return created_edge


@router.patch(
    "/item-relationships/{child_id}",
    response_model=ItemRelationshipOut,
    dependencies=[_manage],
)
def update_item_relationship(
    child_id: UUID,
    updates: ItemRelationshipUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    updated_edge = update_item_relationship_by_child_id(child_id, current_user.userOrg, updates, db)
    db.commit()
    return updated_edge


@router.delete(
    "/item-relationships/{child_id}", status_code=204, dependencies=[_manage]
)
def delete_item_relationship(
    child_id: UUID,
    relationship_type: RelationshipType = "parent_of",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deleted = delete_item_relationship_by_child_id(child_id, current_user.userOrg, db, relationship_type)
    if not deleted:
        raise HTTPException(status_code=404, detail="no such edge")
    db.commit()


@router.delete("/item-relationships/nodes/{item_id}", dependencies=[_manage])
def delete_hierarchy_node(
    item_id: UUID,
    relationship_type: RelationshipType = "parent_of",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Removes item_id from the hierarchy entirely (not just one edge) —
    reparents its children to its own parent. See hierarchy/mutations.py's
    delete_node for the exact behavior. Does not delete the menu_items row."""
    result = delete_node_from_hierarchy(item_id, current_user.userOrg, db, relationship_type)
    db.commit()
    return result
