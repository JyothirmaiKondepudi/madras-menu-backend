from sqlalchemy.orm import Session
from uuid import UUID
from services.menu_items import (
    menu_items_query,
    add_new_menu_item,
    delete_menu_item_by_id,
    get_menu_item_by_id,
    update_menu_item_by_id,
)
from fastapi import APIRouter, Depends, HTTPException, Query
from models import MenuItem
from services.listing import Listing, Page, paginate
from models import User
from schemas.menu_item import MenuItemOut, MenuItemCreate, MenuItemUpdate
from database import get_db
from auth.dependencies import get_current_user, require_permission

router = APIRouter()

# Reads: open to any authenticated user (client, staff, vendor alike) —
# browsing the dish catalog isn't sensitive the way tax rates or the raw
# user directory are. Writes: vendor-only, matching "vendor manages the dish
# library" from the project's business rules.


MENU_ITEM_SORTS = {
    "name": MenuItem.name,
    "course": MenuItem.course,
    "costPerPerson": MenuItem.costPerPerson,
    "createdAt": MenuItem.createdAt,
}


@router.get("/menu-items", response_model=Page[MenuItemOut])
def get_menu_items(
    listing: Listing,
    course: str | None = None,
    veg_nonveg: str | None = Query(None, alias="vegNonveg"),
    active: bool | None = None,
    search: str | None = Query(None, description="part of the dish name"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = menu_items_query()
    if course is not None:
        stmt = stmt.where(MenuItem.course == course)
    if veg_nonveg is not None:
        stmt = stmt.where(MenuItem.vegNonveg == veg_nonveg)
    if active is not None:
        stmt = stmt.where(MenuItem.active == active)
    if search:
        stmt = stmt.where(MenuItem.name.ilike(f"%{search}%"))
    return paginate(db, stmt, listing, MENU_ITEM_SORTS, "name", MenuItem.id)


@router.get("/menu-items/{item_id}", response_model=MenuItemOut)
def get_menu_item(
    item_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = get_menu_item_by_id(item_id, db)
    if item is None:
        raise HTTPException(status_code=404, detail="menu item not found")
    return item


@router.post(
    "/menu-items",
    response_model=MenuItemOut,
    dependencies=[Depends(require_permission("menu_item:create"))],
)
def add_menu_item(new_item: MenuItemCreate, db: Session = Depends(get_db)):
    created_item = add_new_menu_item(new_item, db)
    db.commit()
    return created_item


@router.patch(
    "/menu-items/{item_id}",
    response_model=MenuItemOut,
    dependencies=[Depends(require_permission("menu_item:update"))],
)
def update_menu_item(
    item_id: UUID, updates: MenuItemUpdate, db: Session = Depends(get_db)
):
    updated_item = update_menu_item_by_id(item_id, updates, db)
    if updated_item is None:
        raise HTTPException(status_code=404, detail="menu item not found")
    db.commit()
    return updated_item


@router.delete(
    "/menu-items/{item_id}",
    status_code=204,
    dependencies=[Depends(require_permission("menu_item:delete"))],
)
def delete_menu_item(item_id: UUID, db: Session = Depends(get_db)):
    deleted_item = delete_menu_item_by_id(item_id, db)
    if deleted_item is None:
        raise HTTPException(status_code=404, detail="menu item not found")
    db.commit()
