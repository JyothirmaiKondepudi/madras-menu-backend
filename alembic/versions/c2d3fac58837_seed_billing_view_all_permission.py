"""seed billing permissions

Revision ID: c2d3fac58837
Revises: 53192ce76860
Create Date: 2026-09-26 16:59:53.265524

A one-off insert for the new permissions added to auth/permissions.py for
the billing feature (billing:view_all, billing:create), granted to
"vendor" — the original seed migration (f9c2faedaeb0) is already
shipped/merged, so it can't be edited in place to pick these up; every
later addition to PERMISSIONS gets its own small migration like this one
instead.
"""
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c2d3fac58837'
down_revision: Union[str, Sequence[str], None] = '53192ce76860'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW_PERMISSIONS = [
    ("billing:view_all", "View any subproject's billing history/info, not just your own"),
    ("billing:create", "Record a billing transaction (e.g. a manually-entered payment)"),
]

permissions_table = sa.table(
    "permissions",
    sa.column("id", sa.UUID),
    sa.column("name", sa.String),
    sa.column("description", sa.String),
)
role_permissions_table = sa.table(
    "role_permissions",
    sa.column("role", sa.String),
    sa.column("permission_id", sa.UUID),
)


def upgrade() -> None:
    """Upgrade schema."""
    permission_rows = [{"id": uuid.uuid4(), "name": name, "description": desc} for name, desc in NEW_PERMISSIONS]
    op.bulk_insert(permissions_table, permission_rows)
    op.bulk_insert(
        role_permissions_table,
        [{"role": "vendor", "permission_id": row["id"]} for row in permission_rows],
    )


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    names = [name for name, _ in NEW_PERMISSIONS]
    conn.execute(
        sa.text(
            "DELETE FROM role_permissions WHERE permission_id IN "
            "(SELECT id FROM permissions WHERE name = ANY(:names))"
        ),
        {"names": names},
    )
    conn.execute(sa.text("DELETE FROM permissions WHERE name = ANY(:names)"), {"names": names})
