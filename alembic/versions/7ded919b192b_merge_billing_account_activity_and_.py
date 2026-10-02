"""merge billing, account_activity and organizations heads

Revision ID: 7ded919b192b
Revises: b336bf1a0359, c2d3fac58837, cb678f59a679
Create Date: 2026-10-02 14:12:01.558988

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7ded919b192b'
down_revision: Union[str, Sequence[str], None] = ('b336bf1a0359', 'c2d3fac58837', 'cb678f59a679')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
