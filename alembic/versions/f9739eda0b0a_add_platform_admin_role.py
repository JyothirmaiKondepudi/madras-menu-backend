"""add platform_admin role

Revision ID: f9739eda0b0a
Revises: d752d056b5e8
Create Date: 2026-10-04 18:30:00.000000

Matches ROLE_PERMISSIONS in auth/permissions.py. Data only; no schema change.
- adds the user:grant_platform_admin permission
- grants the new platform_admin role every permission
- makes org management (create/delete/list) platform-only by removing it
  from vendors; vendors keep org:update for their own org
Platform admins are still scoped to their own org's data by the
load_*_in_org checks; these permissions control what actions they may take.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f9739eda0b0a'
down_revision: Union[str, Sequence[str], None] = 'd752d056b5e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PLATFORM_ONLY_ORG_PERMISSIONS = "('org:create', 'org:delete', 'org:list')"


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        """
        INSERT INTO permissions (id, name, description)
        VALUES (gen_random_uuid(), 'user:grant_platform_admin', 'Create users with the platform_admin role')
        ON CONFLICT (name) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO role_permissions (role, permission_id)
        SELECT 'platform_admin', id FROM permissions
        ON CONFLICT DO NOTHING
        """
    )
    op.execute(
        f"""
        DELETE FROM role_permissions
        WHERE role = 'vendor'
          AND permission_id IN (SELECT id FROM permissions WHERE name IN {PLATFORM_ONLY_ORG_PERMISSIONS})
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        f"""
        INSERT INTO role_permissions (role, permission_id)
        SELECT 'vendor', id FROM permissions WHERE name IN {PLATFORM_ONLY_ORG_PERMISSIONS}
        ON CONFLICT DO NOTHING
        """
    )
    op.execute("DELETE FROM role_permissions WHERE role = 'platform_admin'")
    op.execute("DELETE FROM permissions WHERE name = 'user:grant_platform_admin'")
