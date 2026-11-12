"""add no_active_invoices billing status

Revision ID: f4c55310bc16
Revises: 605a613b6bcb
Create Date: 2026-10-09 19:13:27.768413

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f4c55310bc16'
down_revision: Union[str, Sequence[str], None] = '605a613b6bcb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # autogenerate doesn't detect new enum values. Postgres 12+ allows this
    # inside the migration's transaction, as long as nothing in the same
    # transaction uses the new value.
    op.execute("ALTER TYPE billing_status_enum ADD VALUE IF NOT EXISTS 'no_active_invoices'")


def downgrade() -> None:
    """Downgrade schema."""
    # Postgres can't drop an enum value, so the type is rebuilt without it.
    # Rows using it go back to what the old code showed for $0 owed.
    op.execute("UPDATE billing_info SET status = 'paid_in_full' WHERE status = 'no_active_invoices'")
    op.execute("ALTER TYPE billing_status_enum RENAME TO billing_status_enum_old")
    op.execute(
        "CREATE TYPE billing_status_enum AS ENUM "
        "('payment_pending', 'partial_payment_received', 'paid_in_full', 'overdue')"
    )
    op.execute(
        "ALTER TABLE billing_info ALTER COLUMN status TYPE billing_status_enum "
        "USING status::text::billing_status_enum"
    )
    op.execute("DROP TYPE billing_status_enum_old")
