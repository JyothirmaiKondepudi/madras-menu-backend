"""use native uuid for menu tables

Revision ID: 6130c6ea72ee
Revises: 6927b896d569
Create Date: 2026-10-05 13:54:22.799533

The menu tables came from Prisma with text IDs; the CRM tables use UUID.
Every existing value is already a UUID string, so each column is cast in
place (id::uuid) and no ID changes. Postgres can't change the type of a
column a foreign key points at, so the four foreign keys are dropped first
and recreated afterwards with their existing rules.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "6130c6ea72ee"
down_revision: Union[str, Sequence[str], None] = "6927b896d569"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TEXT = sa.VARCHAR()
UUID = postgresql.UUID(as_uuid=True)

# (name, table, column, referenced table, onupdate, ondelete)
FOREIGN_KEYS = [
    (
        "menu_items_tax_category_id_fkey",
        "menu_items",
        "tax_category_id",
        "tax_categories",
        "CASCADE",
        "SET NULL",
    ),
    (
        "item_relationships_from_item_id_fkey",
        "item_relationships",
        "from_item_id",
        "menu_items",
        "CASCADE",
        "RESTRICT",
    ),
    (
        "item_relationships_to_item_id_fkey",
        "item_relationships",
        "to_item_id",
        "menu_items",
        "CASCADE",
        "RESTRICT",
    ),
    (
        "menu_item_embeddings_item_id_fkey",
        "menu_item_embeddings",
        "item_id",
        "menu_items",
        None,
        None,
    ),
]

# (table, column, nullable) for every ID column on the menu side
ID_COLUMNS = [
    ("tax_categories", "id", False),
    ("menu_items", "id", False),
    ("menu_items", "tax_category_id", True),
    ("item_relationships", "id", False),
    ("item_relationships", "from_item_id", False),
    ("item_relationships", "to_item_id", False),
    ("menu_item_embeddings", "item_id", False),
]


def _drop_foreign_keys() -> None:
    for name, table, *_ in FOREIGN_KEYS:
        op.drop_constraint(name, table, type_="foreignkey")


def _create_foreign_keys() -> None:
    for name, table, column, referred, onupdate, ondelete in FOREIGN_KEYS:
        op.create_foreign_key(
            name,
            table,
            referred,
            [column],
            ["id"],
            onupdate=onupdate,
            ondelete=ondelete,
        )


def upgrade() -> None:
    """Upgrade schema."""
    _drop_foreign_keys()
    for table, column, nullable in ID_COLUMNS:
        op.alter_column(
            table,
            column,
            existing_type=TEXT,
            type_=UUID,
            existing_nullable=nullable,
            postgresql_using=f"{column}::uuid",
        )
    _create_foreign_keys()


def downgrade() -> None:
    """Downgrade schema."""
    _drop_foreign_keys()
    for table, column, nullable in ID_COLUMNS:
        op.alter_column(
            table,
            column,
            existing_type=UUID,
            type_=TEXT,
            existing_nullable=nullable,
            postgresql_using=f"{column}::text",
        )
    _create_foreign_keys()
