from model import MenuItem
from sqlalchemy import select
from sqlalchemy.orm import Session


def get_all_menu_items(db: Session):
    return db.execute(select(MenuItem)).scalars().all()

def get_menu_item_by_id(item_id, db: Session):
    return db.get(MenuItem, item_id)

def add_new_menu_item(new_item, db: Session):
    created_item = MenuItem(
        name=new_item.name,
        course=new_item.course,
        vegNonveg=new_item.vegNonveg,
        cuisineTags=new_item.cuisineTags,
        priceWeight=new_item.priceWeight,
        isStaple=new_item.isStaple,
        servedAsLiveStation=new_item.servedAsLiveStation,
        allergens=new_item.allergens,
        dietaryFlags=new_item.dietaryFlags,
        religionSuitability=new_item.religionSuitability,
        occasionSuitability=new_item.occasionSuitability,
        spiceLevel=new_item.spiceLevel,
        prepMethod=new_item.prepMethod,
        portionUnit=new_item.portionUnit,
        costPerPerson=new_item.costPerPerson,
        taxCategoryId=new_item.taxCategoryId,
        active=new_item.active,
        confidence=new_item.confidence,
        sourceDocs=new_item.sourceDocs,
    )
    db.add(created_item)
    db.commit()
    db.refresh(created_item)
    return created_item

def update_menu_item_by_id(item_id, updates, db: Session):
    item = db.get(MenuItem, item_id)
    if item is None:
        return None

    for field, value in updates.model_dump(exclude_unset=True).items():
        setattr(item, field, value)

    db.commit()
    db.refresh(item)
    return item

def delete_menu_item_by_id(item_id, db: Session):
    item = db.get(MenuItem, item_id)
    if item is None:
        return None

    db.delete(item)
    db.commit()
    return item
