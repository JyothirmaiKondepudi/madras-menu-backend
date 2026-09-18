from sqlalchemy.orm import Session
from services.menu_items import *
from fastapi import APIRouter, Depends, HTTPException
from schemas.menu_item import MenuItemOut, MenuItemCreate, MenuItemUpdate
from database import get_db

router = APIRouter()

@router.get("/menu-items", response_model=list[MenuItemOut])
def get_menu_items(db: Session = Depends(get_db)):
    return get_all_menu_items(db)

@router.get("/menu-items/{item_id}", response_model=MenuItemOut)
def get_menu_item(item_id: str, db: Session = Depends(get_db)):
    item = get_menu_item_by_id(item_id, db)
    if item is None:
        raise HTTPException(status_code=404, detail="menu item not found")
    return item

@router.post("/menu-items", response_model=MenuItemOut)
def add_menu_item(new_item: MenuItemCreate, db: Session = Depends(get_db)):
    return add_new_menu_item(new_item, db)

@router.patch("/menu-items/{item_id}", response_model=MenuItemOut)
def update_menu_item(item_id: str, updates: MenuItemUpdate, db: Session = Depends(get_db)):
    updated_item = update_menu_item_by_id(item_id, updates, db)
    if updated_item is None:
        raise HTTPException(status_code=404, detail="menu item not found")
    return updated_item

@router.delete("/menu-items/{item_id}", status_code=204)
def delete_menu_item(item_id: str, db: Session = Depends(get_db)):
    deleted_item = delete_menu_item_by_id(item_id, db)
    if deleted_item is None:
        raise HTTPException(status_code=404, detail="menu item not found")
