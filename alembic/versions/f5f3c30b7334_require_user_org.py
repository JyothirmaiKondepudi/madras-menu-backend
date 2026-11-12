"""require user_org

Revision ID: f5f3c30b7334
Revises: b45da87b809c
Create Date: 2026-10-03 17:30:00.000000

Every user now belongs to an org. This fails if any user_data row still has
no org, so clear or fix those rows before upgrading (in dev:
TRUNCATE user_data CASCADE, then run scripts/seed_dev.py).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f5f3c30b7334'
down_revision: Union[str, Sequence[str], None] = 'b45da87b809c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column('user_data', 'user_org', existing_type=sa.UUID(), nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column('user_data', 'user_org', existing_type=sa.UUID(), nullable=True)
