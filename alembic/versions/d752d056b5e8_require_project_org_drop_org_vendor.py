"""require project org, drop org_vendor

Revision ID: d752d056b5e8
Revises: f5f3c30b7334
Create Date: 2026-10-04 14:41:46.716021


Every project must belong to an org. Projects with no org get their
vendor's org first; if any are still empty after that, the NOT NULL step
fails loudly instead of guessing. organizations.org_vendor is dropped:
nothing read it, and a user's org already lives on user_data.user_org.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd752d056b5e8'
down_revision: Union[str, Sequence[str], None] = 'f5f3c30b7334'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        """
        UPDATE projects p SET organization_id = u.user_org
        FROM user_data u
        WHERE p.organization_id IS NULL AND u.user_id = p.vendor_on_project
        """
    )
    op.alter_column('projects', 'organization_id', existing_type=sa.UUID(), nullable=False)

    op.drop_constraint('organizations_org_vendor_fkey', 'organizations', type_='foreignkey')
    op.drop_column('organizations', 'org_vendor')


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column('projects', 'organization_id', existing_type=sa.UUID(), nullable=True)

    op.add_column('organizations', sa.Column('org_vendor', sa.UUID(), nullable=True))
    op.create_foreign_key(
        'organizations_org_vendor_fkey', 'organizations', 'user_data', ['org_vendor'], ['user_id']
    )
    # best effort: point each org back at its earliest vendor
    op.execute(
        """
        UPDATE organizations o SET org_vendor = (
            SELECT u.user_id FROM user_data u
            WHERE u.user_org = o.org_id AND u.role = 'vendor'
            ORDER BY u.created_at LIMIT 1
        )
        """
    )
