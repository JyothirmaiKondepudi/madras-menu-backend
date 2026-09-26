"""rename admin role and project admin to vendor

Revision ID: 8448a1c35490
Revises: e73dd8200d41
Create Date: 2026-09-20 17:39:06.979583

Replaces the "admin" role vocabulary with "vendor" — "client" is
unaffected. Two parts: the schema rename (projects.admin_on_project ->
vendor_on_project, plus its FK constraint) and a real data migration,
since the "admin" role name is a literal string stored in existing
user_data rows, not just a code-level constant.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8448a1c35490'
down_revision: Union[str, Sequence[str], None] = 'e73dd8200d41'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column('projects', 'admin_on_project', new_column_name='vendor_on_project')
    op.execute(
        'ALTER TABLE projects RENAME CONSTRAINT projects_admin_on_project_fkey '
        'TO projects_vendor_on_project_fkey'
    )

    op.execute("UPDATE user_data SET role = 'vendor' WHERE role = 'admin'")
    op.execute("UPDATE role_permissions SET role = 'vendor' WHERE role = 'admin'")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("UPDATE role_permissions SET role = 'admin' WHERE role = 'vendor'")
    op.execute("UPDATE user_data SET role = 'admin' WHERE role = 'vendor'")

    op.execute(
        'ALTER TABLE projects RENAME CONSTRAINT projects_vendor_on_project_fkey '
        'TO projects_admin_on_project_fkey'
    )
    op.alter_column('projects', 'vendor_on_project', new_column_name='admin_on_project')
