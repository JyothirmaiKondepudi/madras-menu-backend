"""Organization-owned catering pricing configuration.

Preserves legacy price_tiers: its rows have no reliable organization mapping.
No organizations, rates, or Madras-specific defaults are inferred or seeded.
"""
from alembic import op
import sqlalchemy as sa

revision = "a7b83c91d204"
down_revision = "0b2e58333f53"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('pricing_tiers',
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('is_base', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('description', sa.String(), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('org_id', sa.UUID(), nullable=False),
    sa.Column('active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('length(trim(name)) > 0', name='pricing_tiers_name_check'),
    sa.CheckConstraint('position >= 0', name='pricing_tiers_position_check'),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.org_id'], name=op.f('pricing_tiers_org_id_fkey'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('org_id', 'id', name='pricing_tiers_org_id_id_key'),
    sa.UniqueConstraint('org_id', 'position', name='pricing_tiers_org_position_key')
    )
    op.create_index('pricing_tiers_one_active_base', 'pricing_tiers', ['org_id'], unique=True, postgresql_where=sa.text('is_base AND active'))
    op.create_index('pricing_tiers_org_name_key', 'pricing_tiers', ['org_id', sa.literal_column('lower(name)')], unique=True)
    op.create_table('pricing_base_rates',
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('price_per_person', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('minimum_charge', sa.Numeric(precision=12, scale=2), server_default='0', nullable=False),
    sa.Column('inclusions', sa.String(), nullable=False),
    sa.Column('event_type', sa.String(), nullable=True),
    sa.Column('service_style', sa.String(), nullable=True),
    sa.Column('diet', sa.String(), nullable=True),
    sa.Column('min_guests', sa.Integer(), server_default='1', nullable=False),
    sa.Column('max_guests', sa.Integer(), nullable=True),
    sa.Column('effective_from', sa.Date(), nullable=False),
    sa.Column('effective_until', sa.Date(), nullable=True),
    sa.Column('currency', sa.String(length=3), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('org_id', sa.UUID(), nullable=False),
    sa.Column('active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name='pricing_base_rates_currency_check'),
    sa.CheckConstraint("diet IN ('Vegan', 'Vegetarian', 'Jain', 'Halal', 'Non-Vegetarian', 'Eggetarian', 'Kosher', 'Gluten-Free', 'Dairy-Free', 'Other')", name='pricing_base_rates_diet_check'),
    sa.CheckConstraint("event_type IN ('Breakfast', 'Wedding Lunch', 'Wedding Dinner', 'Anniversary', 'Birthday', 'Cocktail Hour', 'Mehendi', 'Haldi', 'Ceremony Refreshments', 'Vidai', 'Welcome Dinner', 'Welcome Lunch', 'Baarat', 'Walima', 'Graduation', 'Housewarming', 'High Tea', 'Other')", name='pricing_base_rates_event_check'),
    sa.CheckConstraint("service_style IN ('Buffet', 'Plated', 'Family Style', 'Live Stations', 'Butler Passed', 'Other')", name='pricing_base_rates_style_check'),
    sa.CheckConstraint('effective_until IS NULL OR effective_until > effective_from', name='pricing_base_rates_dates_check'),
    sa.CheckConstraint('length(trim(name)) > 0 AND length(trim(inclusions)) > 0', name='pricing_base_rates_description_check'),
    sa.CheckConstraint('min_guests > 0 AND (max_guests IS NULL OR max_guests >= min_guests)', name='pricing_base_rates_guests_check'),
    sa.CheckConstraint('price_per_person >= 0 AND minimum_charge >= 0', name='pricing_base_rates_amount_check'),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.org_id'], name=op.f('pricing_base_rates_org_id_fkey'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('pricing_base_rates_org_lookup', 'pricing_base_rates', ['org_id', 'active', 'currency', 'effective_from'], unique=False)
    op.create_table('pricing_adjustments',
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('tier_id', sa.UUID(), nullable=True),
    sa.Column('menu_item_id', sa.UUID(), nullable=True),
    sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('charge_unit', sa.String(), nullable=False),
    sa.Column('event_type', sa.String(), nullable=True),
    sa.Column('service_style', sa.String(), nullable=True),
    sa.Column('diet', sa.String(), nullable=True),
    sa.Column('min_guests', sa.Integer(), server_default='1', nullable=False),
    sa.Column('max_guests', sa.Integer(), nullable=True),
    sa.Column('effective_from', sa.Date(), nullable=False),
    sa.Column('effective_until', sa.Date(), nullable=True),
    sa.Column('currency', sa.String(length=3), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('org_id', sa.UUID(), nullable=False),
    sa.Column('active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("charge_unit IN ('guest', 'event')", name='pricing_adjustments_unit_check'),
    sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name='pricing_adjustments_currency_check'),
    sa.CheckConstraint("diet IN ('Vegan', 'Vegetarian', 'Jain', 'Halal', 'Non-Vegetarian', 'Eggetarian', 'Kosher', 'Gluten-Free', 'Dairy-Free', 'Other')", name='pricing_adjustments_diet_check'),
    sa.CheckConstraint("event_type IN ('Breakfast', 'Wedding Lunch', 'Wedding Dinner', 'Anniversary', 'Birthday', 'Cocktail Hour', 'Mehendi', 'Haldi', 'Ceremony Refreshments', 'Vidai', 'Welcome Dinner', 'Welcome Lunch', 'Baarat', 'Walima', 'Graduation', 'Housewarming', 'High Tea', 'Other')", name='pricing_adjustments_event_check'),
    sa.CheckConstraint("service_style IN ('Buffet', 'Plated', 'Family Style', 'Live Stations', 'Butler Passed', 'Other')", name='pricing_adjustments_style_check'),
    sa.CheckConstraint('amount >= 0', name='pricing_adjustments_amount_check'),
    sa.CheckConstraint('effective_until IS NULL OR effective_until > effective_from', name='pricing_adjustments_dates_check'),
    sa.CheckConstraint('length(trim(name)) > 0', name='pricing_adjustments_name_check'),
    sa.CheckConstraint('min_guests > 0 AND (max_guests IS NULL OR max_guests >= min_guests)', name='pricing_adjustments_guests_check'),
    sa.ForeignKeyConstraint(['menu_item_id'], ['menu_items.id'], name=op.f('pricing_adjustments_menu_item_id_fkey'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['org_id', 'tier_id'], ['pricing_tiers.org_id', 'pricing_tiers.id'], name='pricing_adjustments_tier_org_fkey', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.org_id'], name=op.f('pricing_adjustments_org_id_fkey'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('pricing_adjustments_menu_item', 'pricing_adjustments', ['menu_item_id'], unique=False)
    op.create_index('pricing_adjustments_org_lookup', 'pricing_adjustments', ['org_id', 'active', 'currency', 'effective_from'], unique=False)
    op.create_index('pricing_adjustments_org_tier', 'pricing_adjustments', ['org_id', 'tier_id'], unique=False)
    op.create_table('pricing_tier_additions',
    sa.Column('tier_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.String(), nullable=False),
    sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('charge_unit', sa.String(), nullable=False),
    sa.Column('event_type', sa.String(), nullable=True),
    sa.Column('service_style', sa.String(), nullable=True),
    sa.Column('diet', sa.String(), nullable=True),
    sa.Column('min_guests', sa.Integer(), server_default='1', nullable=False),
    sa.Column('max_guests', sa.Integer(), nullable=True),
    sa.Column('effective_from', sa.Date(), nullable=False),
    sa.Column('effective_until', sa.Date(), nullable=True),
    sa.Column('currency', sa.String(length=3), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('org_id', sa.UUID(), nullable=False),
    sa.Column('active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("charge_unit IN ('guest', 'event')", name='pricing_tier_additions_unit_check'),
    sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name='pricing_tier_additions_currency_check'),
    sa.CheckConstraint("diet IN ('Vegan', 'Vegetarian', 'Jain', 'Halal', 'Non-Vegetarian', 'Eggetarian', 'Kosher', 'Gluten-Free', 'Dairy-Free', 'Other')", name='pricing_tier_additions_diet_check'),
    sa.CheckConstraint("event_type IN ('Breakfast', 'Wedding Lunch', 'Wedding Dinner', 'Anniversary', 'Birthday', 'Cocktail Hour', 'Mehendi', 'Haldi', 'Ceremony Refreshments', 'Vidai', 'Welcome Dinner', 'Welcome Lunch', 'Baarat', 'Walima', 'Graduation', 'Housewarming', 'High Tea', 'Other')", name='pricing_tier_additions_event_check'),
    sa.CheckConstraint("service_style IN ('Buffet', 'Plated', 'Family Style', 'Live Stations', 'Butler Passed', 'Other')", name='pricing_tier_additions_style_check'),
    sa.CheckConstraint('amount >= 0', name='pricing_tier_additions_amount_check'),
    sa.CheckConstraint('effective_until IS NULL OR effective_until > effective_from', name='pricing_tier_additions_dates_check'),
    sa.CheckConstraint('length(trim(name)) > 0 AND length(trim(description)) > 0', name='pricing_tier_additions_description_check'),
    sa.CheckConstraint('min_guests > 0 AND (max_guests IS NULL OR max_guests >= min_guests)', name='pricing_tier_additions_guests_check'),
    sa.ForeignKeyConstraint(['org_id', 'tier_id'], ['pricing_tiers.org_id', 'pricing_tiers.id'], name='pricing_tier_additions_tier_org_fkey', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.org_id'], name=op.f('pricing_tier_additions_org_id_fkey'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('pricing_tier_additions_org_lookup', 'pricing_tier_additions', ['org_id', 'active', 'currency', 'effective_from'], unique=False)
    op.create_index('pricing_tier_additions_org_tier', 'pricing_tier_additions', ['org_id', 'tier_id'], unique=False)


def downgrade():
    op.drop_table("pricing_tier_additions")
    op.drop_table("pricing_adjustments")
    op.drop_table("pricing_base_rates")
    op.drop_table("pricing_tiers")
