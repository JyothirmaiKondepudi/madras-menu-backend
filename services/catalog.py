"""Rate card and equipment (BE-07): CRUD scoped to the caller's organization.
The two lists work the same way, so they share these functions."""

from sqlalchemy import select
from sqlalchemy.orm import Session


def catalog_query(model, org_id):
    return select(model).where(model.orgId == org_id)


def get_in_org(model, item_id, org_id, db: Session):
    """None if it doesn't exist or belongs to another organization: the
    route answers 404 either way, so other orgs' ids aren't revealed."""
    item = db.get(model, item_id)
    if item is None or item.orgId != org_id:
        return None
    return item


def create_item(model, data, org_id, db: Session):
    item = model(orgId=org_id, **data.model_dump())
    db.add(item)
    db.flush()
    db.refresh(item)
    return item


def update_item(item, updates, db: Session):
    for field, value in updates.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.flush()
    db.refresh(item)
    return item


def delete_item(item, db: Session) -> None:
    db.delete(item)
    db.flush()
