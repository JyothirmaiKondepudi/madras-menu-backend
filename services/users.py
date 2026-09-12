from model import User
from sqlalchemy.orm import Session
from schemas.user import UserUpdate

# maps each UserUpdate/UserCreate field name to the ORM attribute it corresponds to
USER_FIELD_MAP = {
    "fullName": "fullName",
    "email": "userEmail",
    "phoneNumber": "userPhoneNumber",
    "preferredContact": "preferredContact",
    "address": "userAddress",
    "role": "userRole",
}

def get_all_users(db:Session):
    return db.query(User).all()

def get_user_by_user_id(user_id, db:Session):
    return db.query(User).get(user_id)

def add_new_user(user, db:Session):
    existing_user = db.query(User).filter_by(userEmail=user.email).first()
    if existing_user is not None:
        return None
    
    print(f" {user.email} is not an exsiting user. creating anew user. ")
    created_user = User(
        fullName=user.fullName,
        userEmail=user.email,
        userPhoneNumber=user.phoneNumber,
        preferredContact=user.preferredContact,
        userAddress=user.address,
        userRole=user.role,
    )
    db.add(created_user)
    db.commit()
    print(f"commited to databse succesfully")
    db.refresh(created_user)
    return created_user

def update_user_by_user_id(user_id, updates: UserUpdate, db: Session):
    user = db.query(User).get(user_id)
    if user is None:
        return None

    for field, value in updates.model_dump(exclude_unset=True).items():
        setattr(user, USER_FIELD_MAP[field], value)
    print(f"updated user: {updates}")
    db.commit()
    db.refresh(user)
    return user

def delete_user_by_user_id(user_id, db: Session):
    user = db.query(User).get(user_id)
    if user is None:
        return None

    db.delete(user)
    db.commit()
    return user