"""rename service to subproject

Revision ID: e73dd8200d41
Revises: 1cfdedc97efd
Create Date: 2026-09-20 17:38:47.701583

Pure rename — the "Service" entity (a catering engagement under a
project) is being renamed to "Subproject" to stop colliding with the
service-*layer* convention (services/users.py, services/invoices.py,
etc.). No column is added, dropped, or retyped; every row is preserved.
The 'venue' column and 'venue_enum'/'religion_enum'/'event_enum' types
keep their names since they were never "service"-prefixed to begin with.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e73dd8200d41'
down_revision: Union[str, Sequence[str], None] = '1cfdedc97efd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.rename_table('services', 'subprojects')
    op.alter_column('subprojects', 'service_id', new_column_name='subproject_id')
    op.alter_column('subprojects', 'service_name', new_column_name='subproject_name')
    op.alter_column('subprojects', 'service_date', new_column_name='subproject_date')
    op.alter_column('subprojects', 'service_type', new_column_name='subproject_type')
    op.alter_column('subprojects', 'service_event', new_column_name='subproject_event')

    op.execute('ALTER TYPE service_type_enum RENAME TO subproject_type_enum')

    op.execute('ALTER INDEX services_pkey RENAME TO subprojects_pkey')
    op.execute(
        'ALTER TABLE subprojects RENAME CONSTRAINT services_project_associated_to_fkey '
        'TO subprojects_project_associated_to_fkey'
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        'ALTER TABLE subprojects RENAME CONSTRAINT subprojects_project_associated_to_fkey '
        'TO services_project_associated_to_fkey'
    )
    op.execute('ALTER INDEX subprojects_pkey RENAME TO services_pkey')

    op.execute('ALTER TYPE subproject_type_enum RENAME TO service_type_enum')

    op.alter_column('subprojects', 'subproject_event', new_column_name='service_event')
    op.alter_column('subprojects', 'subproject_type', new_column_name='service_type')
    op.alter_column('subprojects', 'subproject_date', new_column_name='service_date')
    op.alter_column('subprojects', 'subproject_name', new_column_name='service_name')
    op.alter_column('subprojects', 'subproject_id', new_column_name='service_id')
    op.rename_table('subprojects', 'services')
