from models import ItemRelationship
from sqlalchemy import select
from sqlalchemy.orm import Session

from hierarchy.mutations import insert_edge, update_edge, delete_edge, delete_node


def item_relationships_query():
    return select(ItemRelationship)


def get_item_relationship_by_child_id(child_id, db: Session, relationship_type="parent_of"):
    return db.execute(
        select(ItemRelationship).where(
            ItemRelationship.fromItemId == child_id,
            ItemRelationship.relationshipType == relationship_type,
        )
    ).scalars().first()

def add_new_item_relationship(new_edge, db: Session):
    cur = db.connection().connection.cursor()
    edge_id = insert_edge(
        cur,
        child_id=new_edge.childId,
        parent_id=new_edge.parentId,
        relationship_type=new_edge.relationshipType,
        confidence=new_edge.confidence,
        reason=new_edge.reason,
    )
    # written through a raw cursor, around the ORM: reload in case an older
    # copy of the row is already in this session
    return db.get(ItemRelationship, edge_id, populate_existing=True)

def update_item_relationship_by_child_id(child_id, updates, db: Session):
    cur = db.connection().connection.cursor()
    edge_id = update_edge(
        cur,
        child_id=child_id,
        new_parent_id=updates.newParentId,
        relationship_type=updates.relationshipType,
        confidence=updates.confidence,
        reason=updates.reason,
    )
    # written through a raw cursor, around the ORM: reload in case an older
    # copy of the row is already in this session
    return db.get(ItemRelationship, edge_id, populate_existing=True)

def delete_item_relationship_by_child_id(child_id, db: Session, relationship_type="parent_of"):
    cur = db.connection().connection.cursor()
    deleted = delete_edge(cur, child_id, relationship_type)
    return deleted

def delete_node_from_hierarchy(item_id, db: Session, relationship_type="parent_of"):
    cur = db.connection().connection.cursor()
    result = delete_node(cur, item_id, relationship_type)
    return result
