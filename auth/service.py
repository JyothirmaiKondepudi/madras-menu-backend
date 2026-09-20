from sqlalchemy.orm import Session

from models import User
from services.users import get_user_by_email
from auth.security import verify_password, hash_password


def authenticate_user(email: str, password: str, db: Session):
    """Returns the User on success, None on any failure (unknown email or
    wrong password alike) — the route layer turns None into a single
    generic 401 so a failed login never reveals which of the two it was."""
    user = get_user_by_email(email.strip(), db)
    if user is None or user.passwordHash is None:
        return None
    if not verify_password(password, user.passwordHash):
        return None
    return user


def change_password(user: User, current_password: str, new_password: str, db: Session) -> bool:
    """Returns False (and changes nothing) if current_password is wrong or
    the account has no password set at all — same "fail closed, don't
    distinguish why" spirit as authenticate_user. True on success, after
    the new hash is committed."""
    if user.passwordHash is None or not verify_password(current_password, user.passwordHash):
        return False
    user.passwordHash = hash_password(new_password)
    db.commit()
    return True
