from models import ItemRelationship
from sqlalchemy import select
from sqlalchemy.orm import Session

from hierarchy.mutations import insert_edge, update_edge, delete_edge, delete_node


def item_relationships_query(org_id):
    return select(ItemRelationship).where(ItemRelationship.orgId == org_id)


def get_item_relationship_by_child_id(child_id, org_id, db: Session, relationship_type="parent_of"):
    return db.execute(
        select(ItemRelationship).where(
            ItemRelationship.orgId == org_id,
            ItemRelationship.fromItemId == child_id,
            ItemRelationship.relationshipType == relationship_type,
        )
    ).scalars().first()

def add_new_item_relationship(new_edge, org_id, db: Session):
    return insert_edge(
        db,
        org_id,
        child_id=new_edge.childId,
        parent_id=new_edge.parentId,
        relationship_type=new_edge.relationshipType,
        confidence=new_edge.confidence,
        reason=new_edge.reason,
    )


def update_item_relationship_by_child_id(child_id, org_id, updates, db: Session):
    return update_edge(
        db,
        org_id,
        child_id=child_id,
        new_parent_id=updates.newParentId,
        relationship_type=updates.relationshipType,
        confidence=updates.confidence,
        reason=updates.reason,
    )


def delete_item_relationship_by_child_id(child_id, org_id, db: Session, relationship_type="parent_of"):
    return delete_edge(db, org_id, child_id, relationship_type)


def delete_node_from_hierarchy(item_id, org_id, db: Session, relationship_type="parent_of"):
    return delete_node(db, org_id, item_id, relationship_type)
