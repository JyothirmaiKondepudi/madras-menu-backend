"""catering brief on subprojects and Other options

BE-05: adds venue name and address, diet (a list from a fixed set), allergies,
theme and theme notes to subprojects, and an "Other" choice to service style,
venue and event type. The value lists are copied here rather than imported
from models/choices.py so later edits there can't change this migration.

Revision ID: 28ddb3efcc3b
Revises: 2f01c1eca60c
Create Date: 2026-10-18 11:37:56.045465

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '28ddb3efcc3b'
down_revision: Union[str, Sequence[str], None] = '2f01c1eca60c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SERVICE_STYLES = ["Buffet", "Plated", "Family Style", "Live Stations", "Butler Passed"]
VENUES = ["Hotel", "Country Club", "Museum", "Party Hall", "Home", "Outdoor"]
EVENT_TYPES = [
    "Breakfast", "Wedding Lunch", "Wedding Dinner", "Anniversary", "Birthday",
    "Cocktail Hour", "Mehendi", "Haldi", "Ceremony Refreshments", "Vidai",
    "Welcome Dinner", "Welcome Lunch", "Baarat", "Walima", "Graduation",
    "Housewarming", "High Tea",
]
DIETS = [
    "Vegan", "Vegetarian", "Jain", "Halal", "Non-Vegetarian", "Eggetarian",
    "Kosher", "Gluten-Free", "Dairy-Free", "Other",
]

# column -> its values before this migration ("Other" is added on upgrade)
CHOICE_COLUMNS = {
    "subproject_type": SERVICE_STYLES,
    "venue": VENUES,
    "subproject_event": EVENT_TYPES,
}


def _quoted(values):
    return ", ".join(f"'{v}'" for v in values)


def _replace_check(column, values):
    name = f"subprojects_{column}_check"
    op.drop_constraint(name, "subprojects", type_="check")
    op.create_check_constraint(name, "subprojects", f"{column} IN ({_quoted(values)})")


def upgrade() -> None:
    op.add_column("subprojects", sa.Column("venue_name", sa.String(), nullable=True))
    op.add_column("subprojects", sa.Column("venue_address", sa.String(), nullable=True))
    op.add_column("subprojects", sa.Column(
        "diet", sa.ARRAY(sa.String()), server_default=sa.text("'{}'"), nullable=False
    ))
    op.add_column("subprojects", sa.Column(
        "allergies", sa.ARRAY(sa.String()), server_default=sa.text("'{}'"), nullable=False
    ))
    op.add_column("subprojects", sa.Column("theme", sa.String(), nullable=True))
    op.add_column("subprojects", sa.Column("theme_notes", sa.String(), nullable=True))
    op.create_check_constraint(
        "subprojects_diet_check", "subprojects", f"diet <@ ARRAY[{_quoted(DIETS)}]::varchar[]"
    )
    for column, values in CHOICE_COLUMNS.items():
        _replace_check(column, values + ["Other"])


def downgrade() -> None:
    # fails if any row uses "Other": change those rows first
    for column, values in CHOICE_COLUMNS.items():
        _replace_check(column, values)
    op.drop_constraint("subprojects_diet_check", "subprojects", type_="check")
    for column in ("theme_notes", "theme", "allergies", "diet", "venue_address", "venue_name"):
        op.drop_column("subprojects", column)
