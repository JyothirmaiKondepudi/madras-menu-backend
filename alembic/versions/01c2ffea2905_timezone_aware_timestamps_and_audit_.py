"""timezone-aware timestamps and audit columns

Revision ID: 01c2ffea2905
Revises: c0c7a67583f4
Create Date: 2026-10-04 19:45:36.621354

- Every naive TIMESTAMP becomes TIMESTAMPTZ. Existing values are read as UTC.
- created_at / updated_at are added to invoices, projects and subprojects,
  and org_updated_at to organizations; existing rows get the migration time.
- Columns that are set by the database get a now() default, and
  created_at / org_created_at on user_data and organizations become NOT NULL.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '01c2ffea2905'
down_revision: Union[str, Sequence[str], None] = 'c0c7a67583f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NAIVE = sa.TIMESTAMP()
AWARE = sa.DateTime(timezone=True)

# (table, column, nullable) for every existing naive timestamp column
NAIVE_COLUMNS = [
    ('account_activity', 'occurred_at', False),
    ('billing_history', 'occurred_at', True),
    ('billing_info', 'last_event_at', False),
    ('item_relationships', 'created_at', False),
    ('menu_item_embeddings', 'created_at', False),
    ('menu_items', 'created_at', False),
    ('menu_items', 'updated_at', False),
    ('organizations', 'org_created_at', True),
    ('projects', 'project_start_date', True),
    ('projects', 'project_end_date', True),
    ('subprojects', 'subproject_date', False),
    ('tax_categories', 'effective_date', False),
    ('user_data', 'created_at', True),
    ('user_data', 'updated_at', True),
]

# existing columns that only had a Python-side default and now default to now()
GAINS_DB_DEFAULT = [
    ('billing_history', 'occurred_at'),
    ('menu_items', 'updated_at'),
    ('organizations', 'org_created_at'),
    ('user_data', 'created_at'),
    ('user_data', 'updated_at'),
]

# existing nullable columns that become NOT NULL (no NULLs in current data)
BECOMES_NOT_NULL = [
    ('organizations', 'org_created_at'),
    ('user_data', 'created_at'),
    ('user_data', 'updated_at'),
]

# (table, column) for the new audit columns
NEW_COLUMNS = [
    ('invoices', 'created_at'),
    ('invoices', 'updated_at'),
    ('projects', 'created_at'),
    ('projects', 'updated_at'),
    ('subprojects', 'created_at'),
    ('subprojects', 'updated_at'),
    ('organizations', 'org_updated_at'),
]


def upgrade() -> None:
    """Upgrade schema."""
    for table, column, nullable in NAIVE_COLUMNS:
        op.alter_column(
            table, column,
            existing_type=NAIVE,
            type_=AWARE,
            existing_nullable=nullable,
            postgresql_using=f"{column} AT TIME ZONE 'UTC'",
        )

    for table, column in GAINS_DB_DEFAULT:
        op.alter_column(table, column, server_default=sa.text('now()'))

    for table, column in BECOMES_NOT_NULL:
        op.alter_column(table, column, existing_type=AWARE, nullable=False)

    for table, column in NEW_COLUMNS:
        op.add_column(
            table,
            sa.Column(column, AWARE, server_default=sa.text('now()'), nullable=False),
        )


def downgrade() -> None:
    """Downgrade schema."""
    for table, column in reversed(NEW_COLUMNS):
        op.drop_column(table, column)

    for table, column in BECOMES_NOT_NULL:
        op.alter_column(table, column, existing_type=AWARE, nullable=True)

    for table, column in GAINS_DB_DEFAULT:
        op.alter_column(table, column, server_default=None)

    for table, column, nullable in reversed(NAIVE_COLUMNS):
        op.alter_column(
            table, column,
            existing_type=AWARE,
            type_=NAIVE,
            existing_nullable=nullable,
            postgresql_using=f"{column} AT TIME ZONE 'UTC'",
        )
