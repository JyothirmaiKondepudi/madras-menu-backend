"""baseline schema

Revision ID: b1717c5e72f7
Revises:
Create Date: 2026-10-02 14:49:03.189637

Replaces the old migration history (e0e2badceeaf .. 7ded919b192b), which
started from the shared Prisma schema and so could never build a database
from empty. This baseline creates every table the backend owns, including
the ones that used to be Prisma-managed (menu_items, item_relationships,
tax_categories, price_tiers, live_stations), and seeds permissions from
auth/permissions.py. The old files are still in git history.
"""
import uuid
from typing import Sequence, Union

from alembic import op
import pgvector.sqlalchemy
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from auth.permissions import PERMISSIONS, ROLE_PERMISSIONS

# revision identifiers, used by Alembic.
revision: str = 'b1717c5e72f7'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # menu_item_embeddings.embedding needs pgvector
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table('live_stations',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('region', sa.String(), nullable=False),
    sa.Column('veg_nonveg', sa.String(), nullable=False),
    sa.Column('price_per_person', sa.Numeric(precision=8, scale=2), nullable=False),
    sa.Column('equipment_needed', sa.ARRAY(sa.String()), server_default=sa.text("'{}'"), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('permissions',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('description', sa.String(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_table('price_tiers',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('occasion_type', sa.String(), nullable=False),
    sa.Column('service_style', sa.String(), nullable=False),
    sa.Column('base_per_person', sa.Numeric(precision=8, scale=2), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('tax_categories',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('jurisdiction', sa.String(), nullable=False),
    sa.Column('rate_percent', sa.Numeric(precision=5, scale=3), nullable=False),
    sa.Column('effective_date', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_table('user_data',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('full_name', sa.String(), nullable=False),
    sa.Column('email', sa.String(), nullable=False),
    sa.Column('phone_number', sa.String(length=10), nullable=False),
    sa.Column('preferred_contact', sa.String(), nullable=False),
    sa.Column('address', sa.String(), nullable=True),
    sa.Column('role', sa.String(), nullable=False),
    sa.Column('password_hash', sa.String(), nullable=True),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.Column('user_org', sa.UUID(), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['user_data.user_id'], ),
    sa.PrimaryKeyConstraint('user_id'),
    sa.UniqueConstraint('email')
    )
    op.create_table('menu_items',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('course', sa.String(), nullable=False),
    sa.Column('veg_nonveg', sa.String(), nullable=False),
    sa.Column('cuisine_tags', sa.ARRAY(sa.String()), nullable=True),
    sa.Column('price_weight', sa.String(), nullable=False),
    sa.Column('is_staple', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('served_as_live_station', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('allergens', sa.ARRAY(sa.String()), server_default=sa.text("'{}'"), nullable=True),
    sa.Column('dietary_flags', sa.ARRAY(sa.String()), server_default=sa.text("'{}'"), nullable=True),
    sa.Column('religion_suitability', sa.ARRAY(sa.String()), server_default=sa.text("'{}'"), nullable=True),
    sa.Column('occasion_suitability', sa.ARRAY(sa.String()), server_default=sa.text("'{}'"), nullable=True),
    sa.Column('spice_level', sa.String(), nullable=True),
    sa.Column('prep_method', sa.String(), nullable=True),
    sa.Column('portion_unit', sa.String(), nullable=True),
    sa.Column('cost_per_person', sa.Numeric(precision=8, scale=2), nullable=True),
    sa.Column('tax_category_id', sa.String(), nullable=True),
    sa.Column('active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('confidence', sa.String(), nullable=True),
    sa.Column('source_docs', sa.ARRAY(sa.String()), server_default=sa.text("'{}'"), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['tax_category_id'], ['tax_categories.id'], onupdate='CASCADE', ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_table('organizations',
    sa.Column('org_id', sa.UUID(), nullable=False),
    sa.Column('org_name', sa.String(), nullable=False),
    sa.Column('org_vendor', sa.UUID(), nullable=True),
    sa.Column('org_created_at', sa.DateTime(), nullable=True),
    sa.Column('org_email', sa.String(), nullable=False),
    sa.Column('org_disabled', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['org_vendor'], ['user_data.user_id'], ),
    sa.PrimaryKeyConstraint('org_id')
    )
    op.create_table('role_permissions',
    sa.Column('role', sa.String(), nullable=False),
    sa.Column('permission_id', sa.UUID(), nullable=False),
    sa.ForeignKeyConstraint(['permission_id'], ['permissions.id'], ),
    sa.PrimaryKeyConstraint('role', 'permission_id')
    )
    op.create_table('item_relationships',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('from_item_id', sa.String(), nullable=False),
    sa.Column('to_item_id', sa.String(), nullable=False),
    sa.Column('relationship_type', sa.String(), nullable=False),
    sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['from_item_id'], ['menu_items.id'], onupdate='CASCADE', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['to_item_id'], ['menu_items.id'], onupdate='CASCADE', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('item_relationships_one_parent_per_child', 'item_relationships', ['from_item_id'], unique=True, postgresql_where=sa.text("relationship_type = 'parent_of'"))
    op.create_table('menu_item_embeddings',
    sa.Column('item_id', sa.String(), nullable=False),
    sa.Column('embedding', pgvector.sqlalchemy.vector.VECTOR(dim=768), nullable=False),
    sa.Column('embedded_text', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['item_id'], ['menu_items.id'], ),
    sa.PrimaryKeyConstraint('item_id')
    )
    op.create_index('menu_item_embeddings_hnsw_cosine', 'menu_item_embeddings', ['embedding'], unique=False, postgresql_using='hnsw', postgresql_ops={'embedding': 'vector_cosine_ops'})
    op.create_table('projects',
    sa.Column('project_name', sa.String(), nullable=False),
    sa.Column('project_id', sa.UUID(), nullable=False),
    sa.Column('project_status', sa.Enum('Proposal', 'Accepted', 'Rejected', 'Suggested Changes', 'Planning', 'Complete', name='project_status_enum'), nullable=True),
    sa.Column('project_start_date', sa.DateTime(), nullable=True),
    sa.Column('project_end_date', sa.DateTime(), nullable=True),
    sa.Column('vendor_on_project', sa.UUID(), nullable=True),
    sa.Column('client_id', sa.UUID(), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=True),
    sa.Column('final_invoice_id', sa.UUID(), nullable=True),
    sa.ForeignKeyConstraint(['client_id'], ['user_data.user_id'], ),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.org_id'], ),
    sa.ForeignKeyConstraint(['vendor_on_project'], ['user_data.user_id'], ),
    sa.PrimaryKeyConstraint('project_id')
    )
    op.create_table('subprojects',
    sa.Column('subproject_id', sa.UUID(), nullable=False),
    sa.Column('subproject_name', sa.String(), nullable=False),
    sa.Column('project_associated_to', sa.UUID(), nullable=False),
    sa.Column('cuisine', sa.ARRAY(sa.String()), nullable=True),
    sa.Column('religion', sa.Enum('Hindu', 'Muslim', 'Christian', name='religion_enum'), nullable=True),
    sa.Column('subproject_date', sa.DateTime(), nullable=False),
    sa.Column('guest_count', sa.Integer(), nullable=False),
    sa.Column('subproject_type', sa.Enum('Buffet', 'Plated', 'Family Style', 'Live Stations', 'Butler Passed', name='subproject_type_enum'), nullable=False),
    sa.Column('venue', sa.Enum('Hotel', 'Country Club', 'Mueseum', 'Party Hall', 'Home', 'Outdoor', name='venue_enum'), nullable=False),
    sa.Column('subproject_event', sa.Enum('breakfast', 'wedding Lunch', 'Wedding Dinner', 'Anniversary', 'birthday', 'cockatail hour', 'mehendi', 'haldi', 'ceremony refreshments', 'vidai', 'welcome dinner', 'welcome lunch', 'baarat', 'Walima', 'Graduation', 'house Warming', 'High tea', name='event_enum'), nullable=False),
    sa.Column('min_price_per_person', sa.Float(), nullable=True),
    sa.Column('max_price_per_person', sa.Float(), nullable=True),
    sa.ForeignKeyConstraint(['project_associated_to'], ['projects.project_id'], ),
    sa.PrimaryKeyConstraint('subproject_id')
    )
    op.create_table('user_projects',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('project_id', sa.UUID(), nullable=False),
    sa.ForeignKeyConstraint(['project_id'], ['projects.project_id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['user_data.user_id'], ),
    sa.PrimaryKeyConstraint('user_id', 'project_id')
    )
    op.create_table('account_activity',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('project_id', sa.UUID(), nullable=True),
    sa.Column('subproject_id', sa.UUID(), nullable=True),
    sa.Column('activity_type', sa.String(), nullable=False),
    sa.Column('description', sa.String(), nullable=False),
    sa.Column('actor_id', sa.UUID(), nullable=True),
    sa.Column('occurred_at', sa.DateTime(), nullable=False),
    sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.ForeignKeyConstraint(['actor_id'], ['user_data.user_id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['project_id'], ['projects.project_id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['subproject_id'], ['subprojects.subproject_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('billing_info',
    sa.Column('subproject_id', sa.UUID(), nullable=False),
    sa.Column('total_invoiced', sa.Float(), nullable=True),
    sa.Column('total_paid', sa.Float(), nullable=True),
    sa.Column('total_refunded', sa.Float(), nullable=True),
    sa.Column('balance_due', sa.Float(), nullable=True),
    sa.Column('status', sa.Enum('payment_pending', 'partial_payment_received', 'paid_in_full', 'overdue', name='billing_status_enum'), nullable=False),
    sa.Column('last_event_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['subproject_id'], ['subprojects.subproject_id'], ),
    sa.PrimaryKeyConstraint('subproject_id')
    )
    op.create_table('invoices',
    sa.Column('invoice_id', sa.UUID(), nullable=False),
    sa.Column('invoice_status', sa.Enum('Generated', 'Assigned', 'Pending', 'Accepted', 'Paid', 'Declined', name='invoice_status_enum'), nullable=False),
    sa.Column('invoice_amount', sa.Float(), nullable=False),
    sa.Column('invoice_assigned_to', sa.UUID(), nullable=False),
    sa.Column('project_associated_to', sa.UUID(), nullable=False),
    sa.Column('subproject_id', sa.UUID(), nullable=True),
    sa.ForeignKeyConstraint(['invoice_assigned_to'], ['user_data.user_id'], ),
    sa.ForeignKeyConstraint(['project_associated_to'], ['projects.project_id'], ),
    sa.ForeignKeyConstraint(['subproject_id'], ['subprojects.subproject_id'], ),
    sa.PrimaryKeyConstraint('invoice_id')
    )
    op.create_table('billing_history',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('invoice_id', sa.UUID(), nullable=False),
    sa.Column('event_type', sa.String(), nullable=False),
    sa.Column('amount', sa.Integer(), nullable=False),
    sa.Column('occurred_at', sa.DateTime(), nullable=True),
    sa.Column('source', sa.Enum('Manual', 'Stripe', name='source_enum'), nullable=False),
    sa.Column('failure_reason', sa.String(), nullable=True),
    sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.ForeignKeyConstraint(['invoice_id'], ['invoices.invoice_id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('notifications',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('type', sa.String(), nullable=False),
    sa.Column('message', sa.String(), nullable=False),
    sa.Column('related_invoice_id', sa.UUID(), nullable=True),
    sa.Column('related_user_id', sa.UUID(), nullable=True),
    sa.Column('seen_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['related_invoice_id'], ['invoices.invoice_id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['related_user_id'], ['user_data.user_id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['user_data.user_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )

    # user_data <-> organizations and projects <-> invoices reference each
    # other, so these two FKs can only be added once both tables exist
    op.create_foreign_key('fk_user_data_user_org', 'user_data', 'organizations', ['user_org'], ['org_id'])
    op.create_foreign_key(
        'fk_projects_final_invoice_id', 'projects', 'invoices', ['final_invoice_id'], ['invoice_id']
    )

    permissions_table = sa.table(
        "permissions",
        sa.column("id", sa.UUID),
        sa.column("name", sa.String),
        sa.column("description", sa.String),
    )
    role_permissions_table = sa.table(
        "role_permissions",
        sa.column("role", sa.String),
        sa.column("permission_id", sa.UUID),
    )
    permission_ids = {name: uuid.uuid4() for name, _ in PERMISSIONS}
    op.bulk_insert(
        permissions_table,
        [{"id": permission_ids[name], "name": name, "description": desc} for name, desc in PERMISSIONS],
    )
    op.bulk_insert(
        role_permissions_table,
        [
            {"role": role, "permission_id": permission_ids[name]}
            for role, names in ROLE_PERMISSIONS.items()
            for name in names
        ],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_projects_final_invoice_id', 'projects', type_='foreignkey')
    op.drop_constraint('fk_user_data_user_org', 'user_data', type_='foreignkey')
    op.drop_table('notifications')
    op.drop_table('billing_history')
    op.drop_table('invoices')
    op.drop_table('billing_info')
    op.drop_table('account_activity')
    op.drop_table('user_projects')
    op.drop_table('subprojects')
    op.drop_table('projects')
    op.drop_index('menu_item_embeddings_hnsw_cosine', table_name='menu_item_embeddings', postgresql_using='hnsw', postgresql_ops={'embedding': 'vector_cosine_ops'})
    op.drop_table('menu_item_embeddings')
    op.drop_index('item_relationships_one_parent_per_child', table_name='item_relationships', postgresql_where=sa.text("relationship_type = 'parent_of'"))
    op.drop_table('item_relationships')
    op.drop_table('role_permissions')
    op.drop_table('organizations')
    op.drop_table('menu_items')
    op.drop_table('user_data')
    op.drop_table('tax_categories')
    op.drop_table('price_tiers')
    op.drop_table('permissions')
    op.drop_table('live_stations')

    # drop_table leaves Postgres enum types behind
    for enum_name in (
        'project_status_enum', 'religion_enum', 'subproject_type_enum', 'venue_enum', 'event_enum',
        'billing_status_enum', 'invoice_status_enum', 'source_enum',
    ):
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
