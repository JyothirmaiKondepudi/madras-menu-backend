"""store all money as numeric dollars

Revision ID: c0c7a67583f4
Revises: cb604f81d85c
Create Date: 2026-10-04 19:06:08.232714

Every money column becomes NUMERIC(12, 2) dollars, so sums are exact and no
code converts between units. Floats are rounded to the cent; payment amounts,
previously integer cents, are divided by 100. deposit_percentage becomes
NUMERIC(5, 2).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c0c7a67583f4'
down_revision: Union[str, Sequence[str], None] = 'cb604f81d85c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MONEY = sa.Numeric(precision=12, scale=2)
PERCENT = sa.Numeric(precision=5, scale=2)

# (table, column, new type, nullable) for every column that was a float
FLOAT_COLUMNS = [
    ('invoices', 'invoice_amount', MONEY, False),
    ('invoices', 'total_amount', MONEY, True),
    ('invoices', 'deposit_percentage', PERCENT, True),
    ('billing_info', 'total_invoiced', MONEY, True),
    ('billing_info', 'total_paid', MONEY, True),
    ('billing_info', 'total_refunded', MONEY, True),
    ('billing_info', 'balance_due', MONEY, True),
    ('subprojects', 'min_price_per_person', MONEY, True),
    ('subprojects', 'max_price_per_person', MONEY, True),
]


def upgrade() -> None:
    """Upgrade schema."""
    for table, column, new_type, nullable in FLOAT_COLUMNS:
        op.alter_column(
            table, column,
            existing_type=sa.DOUBLE_PRECISION(precision=53),
            type_=new_type,
            existing_nullable=nullable,
            postgresql_using=f"round({column}::numeric, 2)",
        )

    # cents -> dollars
    op.alter_column(
        'billing_history', 'amount',
        existing_type=sa.INTEGER(),
        type_=MONEY,
        existing_nullable=False,
        postgresql_using="amount / 100.0",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        'billing_history', 'amount',
        existing_type=MONEY,
        type_=sa.INTEGER(),
        existing_nullable=False,
        postgresql_using="round(amount * 100)::integer",
    )

    for table, column, new_type, nullable in reversed(FLOAT_COLUMNS):
        op.alter_column(
            table, column,
            existing_type=new_type,
            type_=sa.DOUBLE_PRECISION(precision=53),
            existing_nullable=nullable,
            postgresql_using=f"{column}::double precision",
        )
