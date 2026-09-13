from model import TaxCategory
from sqlalchemy import select
from sqlalchemy.orm import Session


def get_all_tax_categories(db: Session):
    return db.execute(select(TaxCategory)).scalars().all()

def get_tax_category_by_id(tax_category_id, db: Session):
    return db.get(TaxCategory, tax_category_id)

def add_new_tax_category(new_category, db: Session):
    created_category = TaxCategory(
        name=new_category.name,
        jurisdiction=new_category.jurisdiction,
        ratePercent=new_category.ratePercent,
    )
    db.add(created_category)
    db.commit()
    db.refresh(created_category)
    return created_category

def update_tax_category_by_id(tax_category_id, updates, db: Session):
    category = db.get(TaxCategory, tax_category_id)
    if category is None:
        return None

    for field, value in updates.model_dump(exclude_unset=True).items():
        setattr(category, field, value)

    db.commit()
    db.refresh(category)
    return category

def delete_tax_category_by_id(tax_category_id, db: Session):
    category = db.get(TaxCategory, tax_category_id)
    if category is None:
        return None

    db.delete(category)
    db.commit()
    return category
