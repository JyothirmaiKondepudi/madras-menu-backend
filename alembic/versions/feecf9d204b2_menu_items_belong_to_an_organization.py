"""menu items belong to an organization

Each caterer gets its own dish catalog:

- menu_items.org_id (required, ON DELETE RESTRICT). Names become unique per
  organization instead of across the app.
- item_relationships.org_id, with composite foreign keys so a parent link
  can only join two dishes of the same organization.

Existing dishes need an organization, and a migration must not guess which
one, so when menu_items has rows the organization is passed in:

    alembic -x dish_org=<org uuid> upgrade head

An empty menu_items table (tests, a fresh server) needs no argument.

Revision ID: feecf9d204b2
Revises: 552b37e24963
Create Date: 2026-11-13

"""
from typing import Sequence, Union

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'feecf9d204b2'
down_revision: Union[str, Sequence[str], None] = '552b37e24963'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _dish_org(conn) -> str | None:
    """The organization to give existing dishes, or None if there are none."""
    dishes = conn.execute(sa.text("SELECT count(*) FROM menu_items")).scalar()
    if not dishes:
        return None
    org = context.get_x_argument(as_dictionary=True).get("dish_org")
    if not org:
        raise RuntimeError(
            f"menu_items has {dishes} dishes and each needs an organization. Run:\n"
            "    alembic -x dish_org=<org uuid> upgrade head"
        )
    found = conn.execute(
        sa.text("SELECT count(*) FROM organizations WHERE org_id = CAST(:org AS uuid)"), {"org": org}
    ).scalar()
    if not found:
        raise RuntimeError(f"No organization with id {org}.")
    return org


def upgrade() -> None:
    conn = op.get_bind()
    org = _dish_org(conn)

    # menu_items: owned by an organization
    op.add_column('menu_items', sa.Column('org_id', sa.UUID(), nullable=True))
    if org:
        conn.execute(sa.text("UPDATE menu_items SET org_id = CAST(:org AS uuid)"), {"org": org})
    op.alter_column('menu_items', 'org_id', nullable=False)
    op.create_foreign_key(
        'menu_items_org_id_fkey', 'menu_items', 'organizations', ['org_id'], ['org_id'], ondelete='RESTRICT',
    )
    op.create_index('ix_menu_items_org_id', 'menu_items', ['org_id'])
    op.drop_constraint('menu_items_name_key', 'menu_items', type_='unique')
    op.create_unique_constraint('menu_items_org_name_key', 'menu_items', ['org_id', 'name'])
    op.create_unique_constraint('menu_items_org_item_key', 'menu_items', ['org_id', 'id'])

    # item_relationships: both dishes in the link belong to one organization
    op.add_column('item_relationships', sa.Column('org_id', sa.UUID(), nullable=True))
    conn.execute(sa.text(
        "UPDATE item_relationships r SET org_id = m.org_id FROM menu_items m WHERE m.id = r.from_item_id"
    ))
    op.alter_column('item_relationships', 'org_id', nullable=False)
    op.create_index('ix_item_relationships_org_id', 'item_relationships', ['org_id'])
    op.drop_constraint('item_relationships_from_item_id_fkey', 'item_relationships', type_='foreignkey')
    op.drop_constraint('item_relationships_to_item_id_fkey', 'item_relationships', type_='foreignkey')
    op.create_foreign_key(
        'item_relationships_from_item_org_fkey', 'item_relationships', 'menu_items',
        ['org_id', 'from_item_id'], ['org_id', 'id'], onupdate='CASCADE', ondelete='RESTRICT',
    )
    op.create_foreign_key(
        'item_relationships_to_item_org_fkey', 'item_relationships', 'menu_items',
        ['org_id', 'to_item_id'], ['org_id', 'id'], onupdate='CASCADE', ondelete='RESTRICT',
    )


def downgrade() -> None:
    conn = op.get_bind()
    shared = conn.execute(sa.text(
        "SELECT count(*) FROM (SELECT name FROM menu_items GROUP BY name HAVING count(*) > 1) d"
    )).scalar()
    if shared:
        raise RuntimeError(
            f"{shared} dish names are used by more than one organization; names must be unique "
            "across the app before downgrading. Rename or delete those dishes first."
        )

    op.drop_constraint('item_relationships_to_item_org_fkey', 'item_relationships', type_='foreignkey')
    op.drop_constraint('item_relationships_from_item_org_fkey', 'item_relationships', type_='foreignkey')
    op.create_foreign_key(
        'item_relationships_from_item_id_fkey', 'item_relationships', 'menu_items',
        ['from_item_id'], ['id'], onupdate='CASCADE', ondelete='RESTRICT',
    )
    op.create_foreign_key(
        'item_relationships_to_item_id_fkey', 'item_relationships', 'menu_items',
        ['to_item_id'], ['id'], onupdate='CASCADE', ondelete='RESTRICT',
    )
    op.drop_index('ix_item_relationships_org_id', table_name='item_relationships')
    op.drop_column('item_relationships', 'org_id')

    op.drop_constraint('menu_items_org_item_key', 'menu_items', type_='unique')
    op.drop_constraint('menu_items_org_name_key', 'menu_items', type_='unique')
    op.create_unique_constraint('menu_items_name_key', 'menu_items', ['name'])
    op.drop_index('ix_menu_items_org_id', table_name='menu_items')
    op.drop_constraint('menu_items_org_id_fkey', 'menu_items', type_='foreignkey')
    op.drop_column('menu_items', 'org_id')
