from models import User, Project, Invoice
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from schemas.user import UserUpdate
from auth.security import hash_password
from services.notifications import create_notification
from services.account_activity import record_activity

from uuid import UUID

# maps each UserUpdate/UserCreate field name to the ORM attribute it corresponds to
USER_FIELD_MAP = {
    "fullName": "fullName",
    "email": "userEmail",
    "phoneNumber": "userPhoneNumber",
    "preferredContact": "preferredContact",
    "address": "userAddress",
    "role": "userRole",
}


def get_all_users(db: Session, org_id: UUID):
    return db.execute(select(User).where(User.userOrg == org_id)).scalars().all()


def get_user_by_user_id(user_id, db: Session):
    return db.get(User, user_id)


def get_user_by_email(email, db: Session):
    # Case-insensitive on purpose (unlike add_new_user's duplicate check
    # below) — this is specifically the lookup auth/service.py uses to log
    # someone in, and login shouldn't fail just because a client typed
    # their email in different casing than however it was originally
    # entered when their account was created.
    return (
        db.execute(select(User).where(func.lower(User.userEmail) == email.lower()))
        .scalars()
        .first()
    )


def add_new_user(user, db: Session, created_by: User):
    existing_user = (
        db.execute(select(User).where(User.userEmail == user.email)).scalars().first()
    )
    if existing_user is not None:
        return None

    created_user = User(
        fullName=user.fullName,
        userEmail=user.email,
        userPhoneNumber=user.phoneNumber,
        preferredContact=user.preferredContact,
        userAddress=user.address,
        userRole=user.role,
        userOrg=created_by.userOrg,
        passwordHash=hash_password(user.password) if user.password else None,
        createdBy=created_by.userId,
    )
    db.add(created_user)
    db.commit()

    db.refresh(created_user)

    # Notify whoever sent this invite — not the new user themselves.
    create_notification(
        db,
        user_id=created_by.userId,
        type="user_created",
        message=f"You added {created_user.fullName} as a new user",
        related_user_id=created_user.userId,
    )
    record_activity(
        db,
        activity_type="user_created",
        description=f"{created_user.fullName} was added as a new user",
        actor_id=created_by.userId,
    )
    return created_user


def update_user_by_user_id(user_id, updates: UserUpdate, db: Session):
    user = db.get(User, user_id)
    if user is None:
        return None

    for field, value in updates.model_dump(exclude_unset=True).items():
        setattr(user, USER_FIELD_MAP[field], value)

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


def get_project_count_for_user(user_id, db):
    return db.scalar(
        select(func.count())
        .select_from(Project)
        .where(Project.vendorOnProject == user_id)
    )


def get_invoice_for_user(user_id, db):
    return db.scalar(
        select(func.count())
        .select_from(Invoice)
        .where(Invoice.invoiceAssignedTo == user_id)
    )


def disable_user_by_id(user_id, db):
    user = db.get(User, user_id)
    if user is None:
        return None
    user.userDisabled = True
    db.commit()
    db.refresh(user)
    return user


def enable_user_by_id(user_id, db):
    user = db.get(User, user_id)
    if user is None:
        return None
    user.userDisabled = False
    db.commit()
    db.refresh(user)
    return user
