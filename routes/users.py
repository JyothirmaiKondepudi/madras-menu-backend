from sqlalchemy.orm import Session
from services.users import *
from fastapi import APIRouter, Depends, HTTPException
from models import User
from schemas.user import UserOut, UserCreate, UserUpdate
from database import get_db
from auth.dependencies import get_current_user, require_permission, user_has_permission
from uuid import UUID

router = APIRouter()

@router.get("/users", response_model=list[UserOut], dependencies=[Depends(require_permission("user:list"))])
def get_users(db: Session = Depends(get_db)):
    users = get_all_users(db)
    return users

@router.get("/users/{user_id}", response_model=UserOut)
def get_user_by_id(
    user_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
     if not user_has_permission(current_user, "user:view_all", db) and user_id != current_user.userId:
         raise HTTPException(status_code=403, detail="cannot view another user's profile")
     user = get_user_by_user_id(user_id, db)
     if user is None:
         raise HTTPException(status_code=404, detail="User not found")
     return user

@router.post("/users", response_model=UserOut, dependencies=[Depends(require_permission("user:create"))])
def add_user(
    new_user: UserCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
     # current_user is used here (unlike the unused-vendor pattern elsewhere)
     # — it's who gets notified as "the one who sent this invite," so it
     # stays a real function parameter, not just a dependencies=[] gate.
     created_user = add_new_user(new_user, db, created_by=current_user.userId)
     if created_user is None:
         raise HTTPException(status_code=409, detail=f"user with email {new_user.email} already exists")
     return created_user

@router.patch("/users/{user_id}", response_model=UserOut, dependencies=[Depends(require_permission("user:update"))])
def update_user(
    user_id: UUID,
    updates: UserUpdate,
    db: Session = Depends(get_db)):
    updated_user = update_user_by_user_id(user_id, updates, db)
    if updated_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return updated_user

@router.delete("/users/{user_id}", status_code=204, dependencies=[Depends(require_permission("user:delete"))])
def delete_user(user_id: UUID, db: Session = Depends(get_db)):
    deleted_user = delete_user_by_user_id(user_id, db)
    if deleted_user is None:
        raise HTTPException(status_code=404, detail="User not found")
