"""added soft delete for invoice

Revision ID: 9b4198f9996e
Revises: 87bba32a3858
Create Date: 2026-10-05 20:35:01.200960

Soft delete for invoices (invoice_deleted_at), voiding for payments
(voided_at, voided_reason) and disabling users (user_disabled), plus the
user:disable and billing:void permissions for vendors and platform admins.
Existing rows start out not deleted, not voided and enabled.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9b4198f9996e'
down_revision: Union[str, Sequence[str], None] = '87bba32a3858'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW_PERMISSIONS = [
    ("user:disable", "Disable or re-enable a user account"),
    ("billing:void", "Void a payment that was recorded by mistake"),
]
GRANTED_TO = ("vendor", "platform_admin")


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('billing_history', sa.Column('voided_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('billing_history', sa.Column('voided_reason', sa.String(), nullable=True))
    op.add_column('invoices', sa.Column('invoice_deleted_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('user_data', sa.Column('user_disabled', sa.Boolean(), server_default=sa.text('false'), nullable=False))

    for name, description in NEW_PERMISSIONS:
        op.execute(
            sa.text(
                "INSERT INTO permissions (id, name, description) "
                "VALUES (gen_random_uuid(), :name, :description) ON CONFLICT (name) DO NOTHING"
            ).bindparams(name=name, description=description)
        )
        for role in GRANTED_TO:
            op.execute(
                sa.text(
                    "INSERT INTO role_permissions (role, permission_id) "
                    "SELECT :role, id FROM permissions WHERE name = :name ON CONFLICT DO NOTHING"
                ).bindparams(role=role, name=name)
            )


def downgrade() -> None:
    """Downgrade schema."""
    # role_permissions -> permissions is RESTRICT, so the grants go first
    for name, _ in NEW_PERMISSIONS:
        op.execute(
            sa.text(
                "DELETE FROM role_permissions WHERE permission_id IN "
                "(SELECT id FROM permissions WHERE name = :name)"
            ).bindparams(name=name)
        )
        op.execute(sa.text("DELETE FROM permissions WHERE name = :name").bindparams(name=name))

    op.drop_column('user_data', 'user_disabled')
    op.drop_column('invoices', 'invoice_deleted_at')
    op.drop_column('billing_history', 'voided_reason')
    op.drop_column('billing_history', 'voided_at')
