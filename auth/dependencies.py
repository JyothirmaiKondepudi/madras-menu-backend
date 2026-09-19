import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from database import get_db
from models import User
from auth.security import decode_access_token

# HTTPBearer, not OAuth2PasswordBearer — login here is a JSON body
# (LoginRequest), not OAuth2's form-encoded username/password, so
# OAuth2PasswordBearer would make Swagger's "Authorize" button assume the
# wrong request shape for this API.
_bearer_scheme = HTTPBearer()

_UNAUTHORIZED = HTTPException(
    status_code=401,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    try:
        user_id = decode_access_token(credentials.credentials)
    except jwt.PyJWTError:
        raise _UNAUTHORIZED

    # Re-fetched from the DB on every request, rather than trusting
    # anything beyond the user id out of the token — a role change or a
    # deleted account takes effect immediately this way, not just once the
    # token happens to expire.
    user = db.get(User, user_id)
    if user is None:
        raise _UNAUTHORIZED
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """For routes that are admin-only outright — user management, tax
    rates, the menu/hierarchy catalog, and every write on
    projects/services/invoices. Distinct from the per-resource scoping
    checks (user_project_ids, invoiceAssignedTo) used on the read routes
    that a non-admin CAN see a restricted slice of."""
    if current_user.userRole != "admin":
        raise HTTPException(status_code=403, detail="admin access required")
    return current_user


def user_project_ids(user: User) -> set:
    """The set of project ids this user is linked to via user_projects —
    the one place this lookup is written, so every route scoping by
    project access (projects/services/invoices) agrees on what "yours"
    means. Irrelevant for admins, who bypass this check entirely."""
    return {p.projectId for p in user.projects}
