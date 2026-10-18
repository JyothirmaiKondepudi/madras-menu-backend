"""hierarchy checks: not own parent, known relationship type

BE-28: database backstops for two rules hierarchy/mutations.py enforces: a
dish can't be its own parent, and the only relationship type is parent_of
(the one-parent-per-child index only covers that type, so any other would
slip past it). Stops with a clear error, changing nothing, if existing rows
already break either rule.

Revision ID: 19ecc4a23c7e
Revises: e67cbdd44732
Create Date: 2026-10-18 17:56:20.458450

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '19ecc4a23c7e'
down_revision: Union[str, Sequence[str], None] = 'e67cbdd44732'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bad = op.get_bind().execute(sa.text(
        "SELECT count(*) FROM item_relationships "
        "WHERE from_item_id = to_item_id OR relationship_type <> 'parent_of'"
    )).scalar_one()
    if bad:
        raise RuntimeError(
            f"{bad} item_relationships rows are their own parent or have a type other "
            "than parent_of; fix or remove them before migrating"
        )
    op.create_check_constraint(
        "item_relationships_not_own_parent_check", "item_relationships", "from_item_id <> to_item_id"
    )
    op.create_check_constraint(
        "item_relationships_relationship_type_check",
        "item_relationships",
        "relationship_type IN ('parent_of')",
    )


def downgrade() -> None:
    op.drop_constraint("item_relationships_relationship_type_check", "item_relationships", type_="check")
    op.drop_constraint("item_relationships_not_own_parent_check", "item_relationships", type_="check")
