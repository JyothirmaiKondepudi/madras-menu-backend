"""A caterer's dish catalog: every function works inside one organization."""
from models import MenuItem
from sqlalchemy import select
from sqlalchemy.orm import Session

from services.catalog import create_item, delete_item, get_in_org, update_item


def menu_items_query(org_id):
    return select(MenuItem).where(MenuItem.orgId == org_id)


def get_menu_item_by_id(item_id, org_id, db: Session):
    """None if it doesn't exist or belongs to another organization."""
    return get_in_org(MenuItem, item_id, org_id, db)


def add_new_menu_item(new_item, org_id, db: Session):
    return create_item(MenuItem, new_item, org_id, db)


def update_menu_item_by_id(item_id, org_id, updates, db: Session):
    item = get_menu_item_by_id(item_id, org_id, db)
    if item is None:
        return None
    return update_item(item, updates, db)


def delete_menu_item_by_id(item_id, org_id, db: Session):
    item = get_menu_item_by_id(item_id, org_id, db)
    if item is None:
        return None
    delete_item(item, db)
    return item
