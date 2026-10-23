"""An organization's rate card and equipment list (BE-07), vendor-only.
Deactivate an item (active=false) to hide it from pickers but keep it;
delete it to remove it for good."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from auth.dependencies import get_current_user, require_permission
from database import get_db
from models import Equipment, RateCardItem, User
from schemas.catalog import (
    EquipmentCreate,
    EquipmentOut,
    EquipmentUpdate,
    RateCardItemCreate,
    RateCardItemOut,
    RateCardItemUpdate,
)
from services.catalog import catalog_query, create_item, delete_item, get_in_org, update_item
from services.listing import Listing, Page, paginate

router = APIRouter()

_rate_card = Depends(require_permission("rate_card:manage"))
_equipment = Depends(require_permission("equipment:manage"))

RATE_CARD_SORTS = {
    "name": RateCardItem.name,
    "price": RateCardItem.price,
    "category": RateCardItem.category,
    "createdAt": RateCardItem.createdAt,
}
EQUIPMENT_SORTS = {
    "name": Equipment.name,
    "amount": Equipment.amount,
    "createdAt": Equipment.createdAt,
}


def _found(item, what: str):
    if item is None:
        raise HTTPException(status_code=404, detail=f"{what} not found")
    return item


# --- rate card ------------------------------------------------------------------


@router.get("/rate-card", response_model=Page[RateCardItemOut], dependencies=[_rate_card])
def list_rate_card(
    listing: Listing,
    active: bool | None = None,
    category: str | None = None,
    search: str | None = Query(None, description="part of the service name"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = catalog_query(RateCardItem, current_user.userOrg)
    if active is not None:
        stmt = stmt.where(RateCardItem.active == active)
    if category is not None:
        stmt = stmt.where(RateCardItem.category == category)
    if search:
        stmt = stmt.where(RateCardItem.name.ilike(f"%{search}%"))
    return paginate(db, stmt, listing, RATE_CARD_SORTS, "name", RateCardItem.id)


@router.post("/rate-card", response_model=RateCardItemOut, dependencies=[_rate_card])
def add_rate_card_item(
    body: RateCardItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = create_item(RateCardItem, body, current_user.userOrg, db)
    db.commit()
    return item


@router.get("/rate-card/{item_id}", response_model=RateCardItemOut, dependencies=[_rate_card])
def get_rate_card_item(
    item_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _found(get_in_org(RateCardItem, item_id, current_user.userOrg, db), "rate card item")


@router.patch("/rate-card/{item_id}", response_model=RateCardItemOut, dependencies=[_rate_card])
def update_rate_card_item(
    item_id: UUID,
    body: RateCardItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = _found(get_in_org(RateCardItem, item_id, current_user.userOrg, db), "rate card item")
    item = update_item(item, body, db)
    db.commit()
    return item


@router.delete("/rate-card/{item_id}", status_code=204, dependencies=[_rate_card])
def delete_rate_card_item(
    item_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = _found(get_in_org(RateCardItem, item_id, current_user.userOrg, db), "rate card item")
    delete_item(item, db)
    db.commit()


# --- equipment --------------------------------------------------------------------


@router.get("/equipment", response_model=Page[EquipmentOut], dependencies=[_equipment])
def list_equipment(
    listing: Listing,
    active: bool | None = None,
    search: str | None = Query(None, description="part of the equipment name"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = catalog_query(Equipment, current_user.userOrg)
    if active is not None:
        stmt = stmt.where(Equipment.active == active)
    if search:
        stmt = stmt.where(Equipment.name.ilike(f"%{search}%"))
    return paginate(db, stmt, listing, EQUIPMENT_SORTS, "name", Equipment.id)


@router.post("/equipment", response_model=EquipmentOut, dependencies=[_equipment])
def add_equipment(
    body: EquipmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = create_item(Equipment, body, current_user.userOrg, db)
    db.commit()
    return item


@router.get("/equipment/{item_id}", response_model=EquipmentOut, dependencies=[_equipment])
def get_equipment(
    item_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _found(get_in_org(Equipment, item_id, current_user.userOrg, db), "equipment")


@router.patch("/equipment/{item_id}", response_model=EquipmentOut, dependencies=[_equipment])
def update_equipment(
    item_id: UUID,
    body: EquipmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = _found(get_in_org(Equipment, item_id, current_user.userOrg, db), "equipment")
    item = update_item(item, body, db)
    db.commit()
    return item


@router.delete("/equipment/{item_id}", status_code=204, dependencies=[_equipment])
def delete_equipment(
    item_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = _found(get_in_org(Equipment, item_id, current_user.userOrg, db), "equipment")
    delete_item(item, db)
    db.commit()
