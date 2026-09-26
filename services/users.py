from models import User
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from schemas.user import UserUpdate
from auth.security import hash_password
from services.notifications import create_notification

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
    return db.execute(select(User)).scalars().all()

def get_user_by_user_id(user_id, db:Session):
    return db.get(User, user_id)

def get_user_by_email(email, db: Session):
    # Case-insensitive on purpose (unlike add_new_user's duplicate check
    # below) — this is specifically the lookup auth/service.py uses to log
    # someone in, and login shouldn't fail just because a client typed
    # their email in different casing than however it was originally
    # entered when their account was created.
    return db.execute(
        select(User).where(func.lower(User.userEmail) == email.lower())
    ).scalars().first()

def add_new_user(user, db: Session, created_by=None):
    existing_user = db.execute(
        select(User).where(User.userEmail == user.email)
    ).scalars().first()
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
        passwordHash=hash_password(user.password) if user.password else None,
        createdBy=created_by,
    )
    db.add(created_user)
    db.commit()
    print(f"commited to databse succesfully")
    db.refresh(created_user)

    # Notify whoever sent this invite — not the new user themselves. Null
    # for the one bootstrap vendor, who was created directly against the
    # database, not through this function at all.
    if created_by is not None:
        create_notification(
            db,
            user_id=created_by,
            type="user_created",
            message=f"You added {created_user.fullName} as a new user",
            related_user_id=created_user.userId,
        )
    return created_user

def update_user_by_user_id(user_id, updates: UserUpdate, db: Session):
    user = db.get(User, user_id)
    if user is None:
        return None

    for field, value in updates.model_dump(exclude_unset=True).items():
        setattr(user, USER_FIELD_MAP[field], value)
    print(f"updated user: {updates}")
    db.commit()
    db.refresh(user)
    return user

def delete_user_by_user_id(user_id, db: Session):
    user = db.get(User, user_id)
    if user is None:
        return None

    db.delete(user)
    db.commit()
    return user
