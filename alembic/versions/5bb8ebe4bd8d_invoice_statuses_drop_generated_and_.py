"""invoice statuses: drop generated and pending

Revision ID: 5bb8ebe4bd8d
Revises: 18eafd4f03ce
Create Date: 2026-10-10 17:49:01.982075

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5bb8ebe4bd8d'
down_revision: Union[str, Sequence[str], None] = '18eafd4f03ce'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


OLD_STATUSES = "('Generated', 'Assigned', 'Pending', 'Accepted', 'Paid', 'Declined')"
NEW_STATUSES = "('Assigned', 'Accepted', 'Paid', 'Declined')"


def _rebuild_status_type(values: str) -> None:
    # Postgres can't drop an enum value, so the type is replaced
    op.execute("ALTER TYPE invoice_status_enum RENAME TO invoice_status_enum_old")
    op.execute(f"CREATE TYPE invoice_status_enum AS ENUM {values}")
    op.execute(
        "ALTER TABLE invoices ALTER COLUMN invoice_status TYPE invoice_status_enum "
        "USING invoice_status::text::invoice_status_enum"
    )
    op.execute("DROP TYPE invoice_status_enum_old")


def upgrade() -> None:
    """Upgrade schema."""
    # invoices always have a client, so Generated meant the same as Assigned;
    # Pending meant accepted and awaiting payment
    op.execute("UPDATE invoices SET invoice_status = 'Assigned' WHERE invoice_status = 'Generated'")
    op.execute("UPDATE invoices SET invoice_status = 'Accepted' WHERE invoice_status = 'Pending'")
    _rebuild_status_type(NEW_STATUSES)


def downgrade() -> None:
    """Downgrade schema."""
    # every current value exists in the old type, so no rows need changing
    _rebuild_status_type(OLD_STATUSES)
