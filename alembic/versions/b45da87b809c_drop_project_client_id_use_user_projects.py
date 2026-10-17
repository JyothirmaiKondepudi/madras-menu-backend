"""drop project client_id, use user_projects

Revision ID: b45da87b809c
Revises: cc9ac029a91e
Create Date: 2026-10-03 16:05:00.668548

user_projects becomes the only record of a project's clients. Every
existing client_id is copied into user_projects before the column is
dropped, so no client loses access to a project they could see before.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b45da87b809c'
down_revision: Union[str, Sequence[str], None] = 'cc9ac029a91e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        """
        INSERT INTO user_projects (user_id, project_id)
        SELECT client_id, project_id FROM projects WHERE client_id IS NOT NULL
        ON CONFLICT DO NOTHING
        """
    )
    op.drop_constraint('projects_client_id_fkey', 'projects', type_='foreignkey')
    op.drop_column('projects', 'client_id')

    # links go with either side, so deleting a project or user never fails on them
    op.drop_constraint('user_projects_user_id_fkey', 'user_projects', type_='foreignkey')
    op.drop_constraint('user_projects_project_id_fkey', 'user_projects', type_='foreignkey')
    op.create_foreign_key(
        'user_projects_project_id_fkey', 'user_projects', 'projects',
        ['project_id'], ['project_id'], ondelete='CASCADE',
    )
    op.create_foreign_key(
        'user_projects_user_id_fkey', 'user_projects', 'user_data',
        ['user_id'], ['user_id'], ondelete='CASCADE',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('user_projects_user_id_fkey', 'user_projects', type_='foreignkey')
    op.drop_constraint('user_projects_project_id_fkey', 'user_projects', type_='foreignkey')
    op.create_foreign_key(
        'user_projects_project_id_fkey', 'user_projects', 'projects', ['project_id'], ['project_id']
    )
    op.create_foreign_key(
        'user_projects_user_id_fkey', 'user_projects', 'user_data', ['user_id'], ['user_id']
    )

    # Nullable on the way back: a project can now have zero or several
    # clients, so there isn't always exactly one to restore.
    op.add_column('projects', sa.Column('client_id', sa.UUID(), nullable=True))
    op.create_foreign_key(
        'projects_client_id_fkey', 'projects', 'user_data', ['client_id'], ['user_id']
    )
    op.execute(
        """
        UPDATE projects p SET client_id = (
            SELECT up.user_id FROM user_projects up
            WHERE up.project_id = p.project_id
            ORDER BY up.user_id LIMIT 1
        )
        """
    )
