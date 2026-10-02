import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_db
from models import User, Permission, RolePermission
from auth.security import decode_access_token

# HTTPBearer, not OAuth2PasswordBearer — login uses a JSON body, not form-encoded fields
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

    # Re-fetched every request so role changes/deletions apply immediately
    user = db.get(User, user_id)
    if user is None:
        raise _UNAUTHORIZED
    return user


def user_has_permission(user: User, permission_name: str, db: Session) -> bool:
    """Table-driven permission check against role_permissions/permissions."""
    return db.execute(
        select(RolePermission)
        .join(Permission, Permission.id == RolePermission.permissionId)
        .where(RolePermission.role == user.userRole, Permission.name == permission_name)
    ).first() is not None


def require_permission(permission_name: str):
    """Dependency factory: Depends(require_permission("project:create"))."""

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
    """Project ids this user is linked to via user_projects."""
    return {p.projectId for p in user.projects}
