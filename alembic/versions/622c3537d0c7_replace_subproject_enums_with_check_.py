"""replace subproject enums with check constraints

Revision ID: 622c3537d0c7
Revises: 9858e3197678
Create Date: 2026-10-05 15:08:25.732925

religion, subproject_type, venue and subproject_event move from native
Postgres enums to text columns with CHECK constraints, so values can be
added or renamed without altering a type. Misspelled and lower-case values
are corrected on the way (Mueseum -> Museum, cockatail hour -> Cocktail Hour,
...). The value lists are copied here rather than imported from
models/choices.py so later edits there can't change this migration.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '622c3537d0c7'
down_revision: Union[str, Sequence[str], None] = '9858e3197678'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (column, enum type, old values, nullable)
ENUM_COLUMNS = [
    ('religion', 'religion_enum', ['Hindu', 'Muslim', 'Christian'], True),
    ('subproject_type', 'subproject_type_enum',
     ['Buffet', 'Plated', 'Family Style', 'Live Stations', 'Butler Passed'], False),
    ('venue', 'venue_enum',
     ['Hotel', 'Country Club', 'Mueseum', 'Party Hall', 'Home', 'Outdoor'], False),
    ('subproject_event', 'event_enum',
     ['breakfast', 'wedding Lunch', 'Wedding Dinner', 'Anniversary', 'birthday',
      'cockatail hour', 'mehendi', 'haldi', 'ceremony refreshments', 'vidai',
      'welcome dinner', 'welcome lunch', 'baarat', 'Walima', 'Graduation',
      'house Warming', 'High tea'], False),
]

# column -> {old value: corrected value}, only for values that change
RENAMES = {
    'venue': {'Mueseum': 'Museum'},
    'subproject_event': {
        'breakfast': 'Breakfast',
        'wedding Lunch': 'Wedding Lunch',
        'birthday': 'Birthday',
        'cockatail hour': 'Cocktail Hour',
        'mehendi': 'Mehendi',
        'haldi': 'Haldi',
        'ceremony refreshments': 'Ceremony Refreshments',
        'vidai': 'Vidai',
        'welcome dinner': 'Welcome Dinner',
        'welcome lunch': 'Welcome Lunch',
        'baarat': 'Baarat',
        'house Warming': 'Housewarming',
        'High tea': 'High Tea',
    },
}


def _new_values(column: str, old_values: list[str]) -> list[str]:
    renames = RENAMES.get(column, {})
    return [renames.get(value, value) for value in old_values]


def _rename(column: str, mapping: dict[str, str]) -> None:
    for old, new in mapping.items():
        op.execute(
            sa.text(f"UPDATE subprojects SET {column} = :new WHERE {column} = :old")
            .bindparams(old=old, new=new)
        )


def _check_name(column: str) -> str:
    return f"subprojects_{column}_check"


def upgrade() -> None:
    """Upgrade schema."""
    for column, enum_name, old_values, nullable in ENUM_COLUMNS:
        op.alter_column(
            'subprojects', column,
            existing_type=postgresql.ENUM(*old_values, name=enum_name),
            type_=sa.String(),
            existing_nullable=nullable,
            postgresql_using=f"{column}::text",
        )
        _rename(column, RENAMES.get(column, {}))
        values = ", ".join(f"'{value}'" for value in _new_values(column, old_values))
        op.create_check_constraint(_check_name(column), 'subprojects', f"{column} IN ({values})")
        postgresql.ENUM(name=enum_name).drop(op.get_bind())


def downgrade() -> None:
    """Downgrade schema."""
    for column, enum_name, old_values, nullable in reversed(ENUM_COLUMNS):
        op.drop_constraint(_check_name(column), 'subprojects', type_='check')
        _rename(column, {new: old for old, new in RENAMES.get(column, {}).items()})
        enum = postgresql.ENUM(*old_values, name=enum_name)
        enum.create(op.get_bind())
        op.alter_column(
            'subprojects', column,
            existing_type=sa.String(),
            type_=enum,
            existing_nullable=nullable,
            postgresql_using=f"{column}::{enum_name}",
        )
