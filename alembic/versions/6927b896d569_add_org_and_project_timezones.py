"""add org and project timezones

Revision ID: 6927b896d569
Revises: 01c2ffea2905
Create Date: 2026-10-04 20:03:28.380669

Event times are read in the venue's timezone: the project's, else the org's.
Existing orgs default to America/New_York; projects default to their org.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6927b896d569'
down_revision: Union[str, Sequence[str], None] = '01c2ffea2905'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('organizations', sa.Column('org_timezone', sa.String(), server_default='America/New_York', nullable=False))
    op.add_column('projects', sa.Column('project_timezone', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('projects', 'project_timezone')
    op.drop_column('organizations', 'org_timezone')
