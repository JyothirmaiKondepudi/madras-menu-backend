"""event types: Sangeet, Late-night Snacks, Engagement, Brunch

Adds four event types from Madras's past menus to the database rules that
limit event names, on subprojects and on the three pricing tables with an
event condition. No rows change. The lists are written out here (not read
from models/choices.py) so this migration keeps doing the same thing if the
list in the code changes later.

Downgrading refuses while any row uses one of the new event types.

Revision ID: c328735b18fd
Revises: feecf9d204b2
Create Date: 2026-11-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c328735b18fd'
down_revision: Union[str, Sequence[str], None] = 'feecf9d204b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OLD = [
    "Breakfast", "Wedding Lunch", "Wedding Dinner", "Anniversary", "Birthday", "Cocktail Hour", "Mehendi",
    "Haldi", "Ceremony Refreshments", "Vidai", "Welcome Dinner", "Welcome Lunch", "Baarat", "Walima",
    "Graduation", "Housewarming", "High Tea", "Other",
]
ADDED = ["Sangeet", "Late-night Snacks", "Engagement", "Brunch"]
NEW = OLD[:-1] + ADDED + OLD[-1:]

# (table, column, constraint)
RULES = [
    ("subprojects", "subproject_event", "subprojects_subproject_event_check"),
    ("pricing_base_rates", "event_type", "pricing_base_rates_event_check"),
    ("pricing_tier_additions", "event_type", "pricing_tier_additions_event_check"),
    ("pricing_adjustments", "event_type", "pricing_adjustments_event_check"),
]


def _check(column: str, values: list[str]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def _replace(values: list[str]) -> None:
    for table, column, name in RULES:
        op.drop_constraint(name, table, type_="check")
        op.create_check_constraint(name, table, _check(column, values))


def upgrade() -> None:
    _replace(NEW)


def downgrade() -> None:
    conn = op.get_bind()
    for table, column, _ in RULES:
        used = conn.execute(
            sa.text(f"SELECT count(*) FROM {table} WHERE {column} = ANY(:added)"), {"added": ADDED}
        ).scalar()
        if used:
            raise RuntimeError(
                f"{used} rows in {table} use one of {', '.join(ADDED)}; change them before downgrading."
            )
    _replace(OLD)
