from sqlalchemy.orm import Session
from services.item_relationships import *
from fastapi import APIRouter, Depends, HTTPException
from schemas.item_relationship import ItemRelationshipOut, ItemRelationshipCreate, ItemRelationshipUpdate
from database import get_db
from auth.dependencies import require_permission
# HierarchyError no longer needs to be caught here — main.py's global
# exception handler turns it into a 400 for every route, not just this one.

router = APIRouter()

# Internal hierarchy/tree tooling — gated by a single "hierarchy:manage"
# permission covering reads and writes alike, same as tax categories,
# not client-facing data.

_manage = Depends(require_permission("hierarchy:manage"))

@router.get("/item-relationships", response_model=list[ItemRelationshipOut], dependencies=[_manage])
def get_item_relationships(db: Session = Depends(get_db)):
    return get_all_item_relationships(db)

@router.get("/item-relationships/{child_id}", response_model=ItemRelationshipOut, dependencies=[_manage])
def get_item_relationship(
    child_id: str, relationship_type: str = "parent_of", db: Session = Depends(get_db)
):
    edge = get_item_relationship_by_child_id(child_id, db, relationship_type)
    if edge is None:
        raise HTTPException(status_code=404, detail="no such edge")
    return edge

@router.post("/item-relationships", response_model=ItemRelationshipOut, dependencies=[_manage])
def add_item_relationship(new_edge: ItemRelationshipCreate, db: Session = Depends(get_db)):
    return add_new_item_relationship(new_edge, db)

@router.patch("/item-relationships/{child_id}", response_model=ItemRelationshipOut, dependencies=[_manage])
def update_item_relationship(child_id: str, updates: ItemRelationshipUpdate, db: Session = Depends(get_db)):
    return update_item_relationship_by_child_id(child_id, updates, db)

@router.delete("/item-relationships/{child_id}", status_code=204, dependencies=[_manage])
def delete_item_relationship(
    child_id: str, relationship_type: str = "parent_of", db: Session = Depends(get_db)
):
    deleted = delete_item_relationship_by_child_id(child_id, db, relationship_type)
    if not deleted:
        raise HTTPException(status_code=404, detail="no such edge")

@router.delete("/item-relationships/nodes/{item_id}", dependencies=[_manage])
def delete_hierarchy_node(item_id: str, relationship_type: str = "parent_of", db: Session = Depends(get_db)):
    """Removes item_id from the hierarchy entirely (not just one edge) —
    reparents its children to its own parent. See hierarchy/mutations.py's
    delete_node for the exact behavior. Does not delete the menu_items row."""
    return delete_node_from_hierarchy(item_id, db, relationship_type)
