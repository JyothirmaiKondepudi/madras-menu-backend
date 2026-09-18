from sqlalchemy.orm import Session
from services.tax_categories import *
from fastapi import APIRouter, Depends, HTTPException
from schemas.tax_category import TaxCategoryOut, TaxCategoryCreate, TaxCategoryUpdate
from database import get_db

router = APIRouter()

@router.get("/tax-categories", response_model=list[TaxCategoryOut])
def get_tax_categories(db: Session = Depends(get_db)):
    return get_all_tax_categories(db)

@router.get("/tax-categories/{tax_category_id}", response_model=TaxCategoryOut)
def get_tax_category(tax_category_id: str, db: Session = Depends(get_db)):
    category = get_tax_category_by_id(tax_category_id, db)
    if category is None:
        raise HTTPException(status_code=404, detail="tax category not found")
    return category

@router.post("/tax-categories", response_model=TaxCategoryOut)
def add_tax_category(new_category: TaxCategoryCreate, db: Session = Depends(get_db)):
    return add_new_tax_category(new_category, db)

@router.patch("/tax-categories/{tax_category_id}", response_model=TaxCategoryOut)
def update_tax_category(tax_category_id: str, updates: TaxCategoryUpdate, db: Session = Depends(get_db)):
    updated_category = update_tax_category_by_id(tax_category_id, updates, db)
    if updated_category is None:
        raise HTTPException(status_code=404, detail="tax category not found")
    return updated_category

@router.delete("/tax-categories/{tax_category_id}", status_code=204)
def delete_tax_category(tax_category_id: str, db: Session = Depends(get_db)):
    deleted_category = delete_tax_category_by_id(tax_category_id, db)
    if deleted_category is None:
        raise HTTPException(status_code=404, detail="tax category not found")
