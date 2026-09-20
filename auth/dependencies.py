import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_db
from models import User, Permission, RolePermission
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


def user_has_permission(user: User, permission_name: str, db: Session) -> bool:
    """Table-driven check against role_permissions/permissions — replaces
    a hardcoded "is this user vendor" test everywhere in the app. A role
    with no matching row simply has no permissions; nothing is implicitly
    vendor. This is the one place this lookup is written, so every route
    checking a permission agrees on what it means."""
    return db.execute(
        select(RolePermission)
        .join(Permission, Permission.id == RolePermission.permissionId)
        .where(RolePermission.role == user.userRole, Permission.name == permission_name)
    ).first() is not None


def require_permission(permission_name: str):
    """Factory — Depends(require_permission("project:create")). The
    table-driven replacement for a hardcoded vendor check: each route
    names the specific permission it needs, so granting a future role
    (staff, chef) a subset of vendor's capabilities is a data change
    (new role_permissions rows) rather than a code change. Distinct from
    the per-resource scoping checks (user_project_ids, invoiceAssignedTo)
    used on routes where a user CAN see a restricted slice of a resource
    they don't have blanket permission for."""

    def _dependency(
        current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
    ) -> User:
        if not user_has_permission(current_user, permission_name, db):
            raise HTTPException(
                status_code=403, detail=f"missing required permission: {permission_name}"
            )
        return current_user

    return _dependency


def user_project_ids(user: User) -> set:
    """The set of project ids this user is linked to via user_projects —
    the one place this lookup is written, so every route scoping by
    project access (projects/services/invoices) agrees on what "yours"
    means. Irrelevant for vendors, who bypass this check entirely."""
    return {p.projectId for p in user.projects}
