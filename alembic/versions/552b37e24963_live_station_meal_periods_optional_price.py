"""live station meal periods, optional price

Adds live_stations.meal_periods (breakfast / lunch / dinner) and lets
price_per_person be NULL, so a caterer's stations can be loaded before they
are priced.

Revision ID: 552b37e24963
Revises: bad71e322a9c
Create Date: 2026-11-12 15:29:24.579002

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '552b37e24963'
down_revision: Union[str, Sequence[str], None] = 'bad71e322a9c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'live_stations',
        sa.Column('meal_periods', sa.ARRAY(sa.String()), server_default=sa.text("'{}'"), nullable=False),
    )
    op.create_check_constraint(
        'live_stations_meal_periods_check', 'live_stations',
        "meal_periods <@ ARRAY['breakfast', 'lunch', 'dinner']::varchar[]",
    )
    op.alter_column(
        'live_stations', 'price_per_person',
        existing_type=sa.NUMERIC(precision=12, scale=2), nullable=True,
    )


def downgrade() -> None:
    unpriced = op.get_bind().execute(
        sa.text("SELECT count(*) FROM live_stations WHERE price_per_person IS NULL")
    ).scalar()
    if unpriced:
        raise RuntimeError(
            f"{unpriced} live stations have no price; set their prices or delete them before downgrading."
        )
    op.alter_column(
        'live_stations', 'price_per_person',
        existing_type=sa.NUMERIC(precision=12, scale=2), nullable=False,
    )
    op.drop_constraint('live_stations_meal_periods_check', 'live_stations', type_='check')
    op.drop_column('live_stations', 'meal_periods')
