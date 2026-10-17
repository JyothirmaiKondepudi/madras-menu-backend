"""invoice relationship constraints

Revision ID: 18eafd4f03ce
Revises: f4c55310bc16
Create Date: 2026-10-10 15:37:01.531177

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '18eafd4f03ce'
down_revision: Union[str, Sequence[str], None] = 'f4c55310bc16'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # the unique pair has to exist before a foreign key can point at it
    # (autogenerate put it last)
    op.create_unique_constraint('subprojects_subproject_id_project_associated_to_key', 'subprojects', ['subproject_id', 'project_associated_to'])
    # the billed client must be linked to the invoice's project
    op.create_foreign_key('invoices_assignee_project_member_fkey', 'invoices', 'user_projects', ['invoice_assigned_to', 'project_associated_to'], ['user_id', 'project_id'], ondelete='RESTRICT')
    # the subproject must belong to the invoice's project (skipped when subproject_id is null)
    op.create_foreign_key('invoices_subproject_in_project_fkey', 'invoices', 'subprojects', ['subproject_id', 'project_associated_to'], ['subproject_id', 'project_associated_to'], ondelete='RESTRICT')


def downgrade() -> None:
    """Downgrade schema."""
    # foreign keys first, then the unique pair they point at
    op.drop_constraint('invoices_subproject_in_project_fkey', 'invoices', type_='foreignkey')
    op.drop_constraint('invoices_assignee_project_member_fkey', 'invoices', type_='foreignkey')
    op.drop_constraint('subprojects_subproject_id_project_associated_to_key', 'subprojects', type_='unique')
