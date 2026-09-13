from sqlalchemy.orm import Session
from services.users import *
from fastapi import APIRouter, Depends, HTTPException
from model import User
from schemas.user import UserOut, UserCreate, UserUpdate
from database import get_db
from uuid import UUID

router = APIRouter()

@router.get("/users",response_model=list[UserOut])
def get_users(db: Session= Depends(get_db)):
    users = get_all_users(db)
    return users

@router.get("/users/{user_id}", response_model=UserOut)
def get_user_by_id(user_id:UUID, db:Session= Depends(get_db)):
     user = get_user_by_user_id(user_id, db)
     if user is None:
         raise HTTPException(status_code=404, detail="User not found")
     return user

@router.post("/users", response_model=UserOut)
def add_user(new_user: UserCreate, db:Session= Depends(get_db)):
     created_user = add_new_user(new_user, db)
     if created_user is None:
         raise HTTPException(status_code=409, detail=f"user with email {new_user.email} already exists")
     return created_user

@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(user_id: UUID, updates: UserUpdate, db: Session = Depends(get_db)):
    updated_user = update_user_by_user_id(user_id, updates, db)
    if updated_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return updated_user

@router.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: UUID, db: Session = Depends(get_db)):
    deleted_user = delete_user_by_user_id(user_id, db)
    if deleted_user is None:
        raise HTTPException(status_code=404, detail="User not found")

