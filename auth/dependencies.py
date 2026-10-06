import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_db
from uuid import UUID
from models import User, Permission, RolePermission, Project, Subproject, Invoice
from auth.security import decode_access_token

# HTTPBearer, not OAuth2PasswordBearer — login uses a JSON body, not form-encoded fields
_bearer_scheme = HTTPBearer()

_UNAUTHORIZED = HTTPException(
    status_code=401,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    request: Request,
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
    if user.userDisabled:
        raise HTTPException(status_code=401, detail="User disabled")
    request.state.user_id = user.userId
    request.state.org_id = user.userOrg
    return user


def user_has_permission(user: User, permission_name: str, db: Session) -> bool:
    """Table-driven permission check against role_permissions/permissions."""
    return (
        db.execute(
            select(RolePermission)
            .join(Permission, Permission.id == RolePermission.permissionId)
            .where(
                RolePermission.role == user.userRole, Permission.name == permission_name
            )
        ).first()
        is not None
    )


def require_permission(permission_name: str):
    """Dependency factory: Depends(require_permission("project:create"))."""

    def _dependency(
        current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
    ) -> User:
        if not user_has_permission(current_user, permission_name, db):
            raise HTTPException(
                status_code=403,
                detail=f"missing required permission: {permission_name}",
            )
        return current_user

    return _dependency


def user_project_ids(user: User) -> set:
    """Project ids this user is linked to via user_projects."""
    return {p.projectId for p in user.projects}


def load_project_in_org(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Project:
    project = db.get(Project, project_id)
    if project is None or project.organizationId != current_user.userOrg:
        raise HTTPException(status_code=404, detail="project not found")
    return project


def load_user_in_org(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    user = db.get(User, user_id)
    if user is None or user.userOrg != current_user.userOrg:
        raise HTTPException(status_code=404, detail="user not found")
    return user


def load_subproject_in_org(
    subproject_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Subproject:
    sub_project = db.get(Subproject, subproject_id)
    if (
        sub_project is None
        or sub_project.project.organizationId != current_user.userOrg
    ):
        raise HTTPException(status_code=404, detail="sub project not found")
    return sub_project


def load_invoice_in_org(
    invoice_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Invoice:
    invoice = db.get(Invoice, invoice_id)
    if (
        invoice is None
        # db.get can return an already-loaded row without the soft-delete filter
        or invoice.invoiceDeletedAt is not None
        or invoice.project.organizationId != current_user.userOrg
    ):
        raise HTTPException(status_code=404, detail="invoice not found")
    return invoice
