"""Who may see what (BE-22).

Permissions are table-driven (role_permissions), and each role's set is
cached here for PERMISSION_CACHE_SECONDS, so most checks don't touch the
database. Granting a role a permission is still just an INSERT into
role_permissions, with no restart; it takes effect within that window.

Routes check access in one of two shapes, each written once here:

- ensure_project_access: has the view-all permission, or is linked to the
  project (a client on it).
- ensure_own_or_permission: has the view-all permission, or the record is
  their own (their profile, their org, an invoice billed to them).
"""

import time

from fastapi import HTTPException
from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from models import Permission, RolePermission, User, user_projects

PERMISSION_CACHE_SECONDS = 60

# role -> (when it was loaded, its permission names). A plain dict: reads and
# whole-entry writes are atomic, and two threads loading the same role at
# once just both query and store the same answer.
_permission_cache: dict[str, tuple[float, frozenset[str]]] = {}


def role_permissions(role: str, db: Session) -> frozenset[str]:
    """Every permission name the role has, from the cache when fresh."""
    now = time.monotonic()
    cached = _permission_cache.get(role)
    if cached is not None and now - cached[0] < PERMISSION_CACHE_SECONDS:
        return cached[1]
    names = frozenset(
        db.execute(
            select(Permission.name)
            .join(RolePermission, RolePermission.permissionId == Permission.id)
            .where(RolePermission.role == role)
        ).scalars()
    )
    _permission_cache[role] = (now, names)
    return names


def clear_permission_cache() -> None:
    """Forget every cached role, e.g. right after changing role_permissions."""
    _permission_cache.clear()


def user_has_permission(user: User, permission_name: str, db: Session) -> bool:
    return permission_name in role_permissions(user.userRole, db)


def is_project_member(user: User, project_id, db: Session) -> bool:
    """Linked to the project via user_projects (a client on it)."""
    return db.scalar(
        select(
            exists().where(
                user_projects.c.user_id == user.userId,
                user_projects.c.project_id == project_id,
            )
        )
    )


def ensure_project_access(
    user: User, project_id, permission: str, db: Session, detail: str
) -> None:
    """403 unless the user has `permission` or is linked to the project."""
    if user_has_permission(user, permission, db) or is_project_member(user, project_id, db):
        return
    raise HTTPException(status_code=403, detail=detail)


def ensure_own_or_permission(
    user: User, is_own: bool, permission: str, db: Session, detail: str
) -> None:
    """403 unless the record is the user's own or they have `permission`.
    The permission is only looked up when it's not their own."""
    if is_own or user_has_permission(user, permission, db):
        return
    raise HTTPException(status_code=403, detail=detail)
