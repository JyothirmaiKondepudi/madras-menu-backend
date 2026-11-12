"""pricing models, tier courses, policies, live stations and quotes

Revision ID: bad71e322a9c
Revises: a7b83c91d204

- pricing_models: one row per caterer per pricing version, naming the pricing
  method. The four existing pricing tables now belong to a model
  (pricing_model_id), and tier names, positions and the base tier are unique
  per model instead of per organization.
- pricing_tier_courses: the course slots a tier includes.
- pricing_adjustments.price_weight: a surcharge per dish class.
- pricing_policies: service charge, gratuity, tax mode, rounding, deposit,
  quote validity; one per model.
- live_stations: now owned by an organization, with a minimum guest count,
  description, active flag and timestamps.
- quotes, quote_lines, quote_dishes: frozen prices offered for a subproject.

The pricing tables and live_stations must be empty: their rows have no
pricing model or organization to assign, so the upgrade stops instead of
guessing.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'bad71e322a9c'
down_revision: Union[str, Sequence[str], None] = 'a7b83c91d204'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PRICE_WEIGHTS = "('light', 'standard', 'premium')"
_CONFIG_TABLES = ['pricing_base_rates', 'pricing_adjustments', 'pricing_tier_additions']


def _require_empty(tables):
    conn = op.get_bind()
    for table in tables:
        if conn.execute(sa.text(f'SELECT EXISTS (SELECT 1 FROM {table})')).scalar():
            raise RuntimeError(
                f'{table} has rows. This migration needs it empty: its rows have no '
                f'pricing model or organization to assign. Move or delete them first.'
            )


def upgrade() -> None:
    _require_empty(['pricing_tiers', *_CONFIG_TABLES, 'live_stations'])

    # --- pricing models -------------------------------------------------
    op.create_table('pricing_models',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('org_id', sa.UUID(), nullable=False),
    sa.Column('method', sa.String(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(), server_default='draft', nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('notes', sa.String(), nullable=True),
    sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("method IN ('tiered_per_guest')", name='pricing_models_method_check'),
    sa.CheckConstraint("status = 'draft' OR published_at IS NOT NULL", name='pricing_models_published_at_check'),
    sa.CheckConstraint("status IN ('draft', 'published', 'retired')", name='pricing_models_status_check'),
    sa.CheckConstraint('length(trim(name)) > 0', name='pricing_models_name_check'),
    sa.CheckConstraint('version > 0', name='pricing_models_version_check'),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.org_id'], name='pricing_models_org_id_fkey', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('org_id', 'id', name='pricing_models_org_id_id_key'),
    sa.UniqueConstraint('org_id', 'version', name='pricing_models_org_version_key')
    )
    op.create_index('pricing_models_one_published', 'pricing_models', ['org_id'], unique=True, postgresql_where=sa.text("status = 'published'"))

    # --- existing config tables join a model ----------------------------
    # The old tier links are (org_id, tier_id); they're replaced by
    # (org_id, pricing_model_id, tier_id) so a link can't cross models.
    op.drop_constraint('pricing_adjustments_tier_org_fkey', 'pricing_adjustments', type_='foreignkey')
    op.drop_constraint('pricing_tier_additions_tier_org_fkey', 'pricing_tier_additions', type_='foreignkey')

    op.add_column('pricing_tiers', sa.Column('pricing_model_id', sa.UUID(), nullable=False))
    op.drop_constraint('pricing_tiers_org_id_id_key', 'pricing_tiers', type_='unique')
    op.drop_constraint('pricing_tiers_org_position_key', 'pricing_tiers', type_='unique')
    op.drop_index('pricing_tiers_org_name_key', table_name='pricing_tiers')
    op.drop_index('pricing_tiers_one_active_base', table_name='pricing_tiers')
    op.create_foreign_key('pricing_tiers_model_org_fkey', 'pricing_tiers', 'pricing_models', ['org_id', 'pricing_model_id'], ['org_id', 'id'], ondelete='CASCADE')
    op.create_unique_constraint('pricing_tiers_org_model_id_key', 'pricing_tiers', ['org_id', 'pricing_model_id', 'id'])
    op.create_unique_constraint('pricing_tiers_model_position_key', 'pricing_tiers', ['pricing_model_id', 'position'])
    op.create_index('pricing_tiers_model_name_key', 'pricing_tiers', ['pricing_model_id', sa.literal_column('lower(name)')], unique=True)
    op.create_index('pricing_tiers_one_active_base', 'pricing_tiers', ['pricing_model_id'], unique=True, postgresql_where=sa.text('is_base AND active'))

    for table in _CONFIG_TABLES:
        op.add_column(table, sa.Column('pricing_model_id', sa.UUID(), nullable=False))
        op.drop_index(f'{table}_org_lookup', table_name=table)
        op.create_index(f'{table}_model_lookup', table, ['pricing_model_id', 'active', 'currency', 'effective_from'], unique=False)
        op.create_foreign_key(f'{table}_model_org_fkey', table, 'pricing_models', ['org_id', 'pricing_model_id'], ['org_id', 'id'], ondelete='CASCADE')
    for table in ['pricing_adjustments', 'pricing_tier_additions']:
        op.drop_index(f'{table}_org_tier', table_name=table)
        op.create_index(f'{table}_model_tier', table, ['pricing_model_id', 'tier_id'], unique=False)
        op.create_foreign_key(f'{table}_tier_fkey', table, 'pricing_tiers', ['org_id', 'pricing_model_id', 'tier_id'], ['org_id', 'pricing_model_id', 'id'], ondelete='CASCADE')

    op.add_column('pricing_adjustments', sa.Column('price_weight', sa.String(), nullable=True))
    op.create_check_constraint('pricing_adjustments_price_weight_check', 'pricing_adjustments', f'price_weight IN {_PRICE_WEIGHTS}')
    op.create_check_constraint('pricing_adjustments_dish_or_class_check', 'pricing_adjustments', 'menu_item_id IS NULL OR price_weight IS NULL')

    # --- tier courses and policies ---------------------------------------
    op.create_table('pricing_tier_courses',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('org_id', sa.UUID(), nullable=False),
    sa.Column('pricing_model_id', sa.UUID(), nullable=False),
    sa.Column('tier_id', sa.UUID(), nullable=False),
    sa.Column('course', sa.String(length=50), nullable=False),
    sa.Column('dish_count', sa.Integer(), nullable=False),
    sa.Column('included_price_weights', sa.ARRAY(sa.String()), server_default=sa.text("'{}'"), nullable=False),
    sa.Column('position', sa.Integer(), server_default='0', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("included_price_weights <@ ARRAY['light', 'standard', 'premium']::varchar[]", name='pricing_tier_courses_price_weights_check'),
    sa.CheckConstraint('dish_count > 0', name='pricing_tier_courses_dish_count_check'),
    sa.CheckConstraint('length(trim(course)) > 0', name='pricing_tier_courses_course_check'),
    sa.CheckConstraint('position >= 0', name='pricing_tier_courses_position_check'),
    sa.ForeignKeyConstraint(['org_id', 'pricing_model_id', 'tier_id'], ['pricing_tiers.org_id', 'pricing_tiers.pricing_model_id', 'pricing_tiers.id'], name='pricing_tier_courses_tier_fkey', ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['org_id', 'pricing_model_id'], ['pricing_models.org_id', 'pricing_models.id'], name='pricing_tier_courses_model_org_fkey', ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.org_id'], name='pricing_tier_courses_org_id_fkey', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('pricing_tier_courses_tier_course_key', 'pricing_tier_courses', ['tier_id', sa.literal_column('lower(course)')], unique=True)

    op.create_table('pricing_policies',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('org_id', sa.UUID(), nullable=False),
    sa.Column('pricing_model_id', sa.UUID(), nullable=False),
    sa.Column('currency', sa.String(length=3), nullable=False),
    sa.Column('service_charge_percent', sa.Numeric(precision=5, scale=2), server_default='0', nullable=False),
    sa.Column('gratuity_percent', sa.Numeric(precision=5, scale=2), server_default='0', nullable=False),
    sa.Column('tax_mode', sa.String(), server_default='per_dish_category', nullable=False),
    sa.Column('flat_tax_percent', sa.Numeric(precision=6, scale=3), nullable=True),
    sa.Column('rounding_increment', sa.Numeric(precision=8, scale=2), server_default='0.01', nullable=False),
    sa.Column('deposit_percent', sa.Numeric(precision=5, scale=2), server_default='0', nullable=False),
    sa.Column('quote_valid_days', sa.Integer(), server_default='30', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("(tax_mode = 'flat_rate') = (flat_tax_percent IS NOT NULL) AND (flat_tax_percent IS NULL OR flat_tax_percent BETWEEN 0 AND 100)", name='pricing_policies_flat_tax_check'),
    sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name='pricing_policies_currency_check'),
    sa.CheckConstraint("tax_mode IN ('per_dish_category', 'flat_rate', 'none')", name='pricing_policies_tax_mode_check'),
    sa.CheckConstraint('quote_valid_days > 0', name='pricing_policies_valid_days_check'),
    sa.CheckConstraint('rounding_increment > 0', name='pricing_policies_rounding_check'),
    sa.CheckConstraint('service_charge_percent BETWEEN 0 AND 100 AND gratuity_percent BETWEEN 0 AND 100 AND deposit_percent BETWEEN 0 AND 100', name='pricing_policies_percent_check'),
    sa.ForeignKeyConstraint(['org_id', 'pricing_model_id'], ['pricing_models.org_id', 'pricing_models.id'], name='pricing_policies_model_org_fkey', ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.org_id'], name='pricing_policies_org_id_fkey', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('pricing_model_id', name='pricing_policies_pricing_model_id_key')
    )

    # --- live stations belong to a caterer -------------------------------
    op.add_column('live_stations', sa.Column('org_id', sa.UUID(), nullable=False))
    op.add_column('live_stations', sa.Column('description', sa.String(), nullable=True))
    op.add_column('live_stations', sa.Column('min_guests', sa.Integer(), server_default='1', nullable=False))
    op.add_column('live_stations', sa.Column('active', sa.Boolean(), server_default=sa.text('true'), nullable=False))
    op.add_column('live_stations', sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False))
    op.add_column('live_stations', sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False))
    op.alter_column('live_stations', 'price_per_person',
               existing_type=sa.NUMERIC(precision=8, scale=2),
               type_=sa.Numeric(precision=12, scale=2),
               existing_nullable=False)
    op.alter_column('live_stations', 'equipment_needed',
               existing_type=postgresql.ARRAY(sa.VARCHAR()),
               nullable=False,
               existing_server_default=sa.text("'{}'::character varying[]"))
    op.create_foreign_key('live_stations_org_id_fkey', 'live_stations', 'organizations', ['org_id'], ['org_id'], ondelete='CASCADE')
    op.create_index('ix_live_stations_org_id', 'live_stations', ['org_id'], unique=False)
    op.create_index('live_stations_org_name_key', 'live_stations', ['org_id', sa.literal_column('lower(name)')], unique=True)
    op.create_check_constraint('live_stations_veg_nonveg_check', 'live_stations', "veg_nonveg IN ('veg', 'nonveg', 'both')")
    op.create_check_constraint('live_stations_price_check', 'live_stations', 'price_per_person >= 0')
    op.create_check_constraint('live_stations_min_guests_check', 'live_stations', 'min_guests > 0')
    op.create_check_constraint('live_stations_name_check', 'live_stations', 'length(trim(name)) > 0')

    # --- quotes -----------------------------------------------------------
    op.create_table('quotes',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('org_id', sa.UUID(), nullable=False),
    sa.Column('subproject_id', sa.UUID(), nullable=False),
    sa.Column('pricing_model_id', sa.UUID(), nullable=False),
    sa.Column('tier_id', sa.UUID(), nullable=True),
    sa.Column('status', sa.String(), server_default='draft', nullable=False),
    sa.Column('guest_count', sa.Integer(), nullable=False),
    sa.Column('currency', sa.String(length=3), nullable=False),
    sa.Column('valid_until', sa.Date(), nullable=True),
    sa.Column('discount_percent', sa.Numeric(precision=5, scale=2), server_default='0', nullable=False),
    sa.Column('subtotal_amount', sa.Numeric(precision=12, scale=2), server_default='0', nullable=False),
    sa.Column('discount_amount', sa.Numeric(precision=12, scale=2), server_default='0', nullable=False),
    sa.Column('service_charge_amount', sa.Numeric(precision=12, scale=2), server_default='0', nullable=False),
    sa.Column('gratuity_amount', sa.Numeric(precision=12, scale=2), server_default='0', nullable=False),
    sa.Column('tax_amount', sa.Numeric(precision=12, scale=2), server_default='0', nullable=False),
    sa.Column('total_amount', sa.Numeric(precision=12, scale=2), server_default='0', nullable=False),
    sa.Column('per_guest_amount', sa.Numeric(precision=12, scale=2), server_default='0', nullable=False),
    sa.Column('notes', sa.String(), nullable=True),
    sa.Column('invoice_id', sa.UUID(), nullable=True),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('accepted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name='quotes_currency_check'),
    sa.CheckConstraint("status <> 'accepted' OR accepted_at IS NOT NULL", name='quotes_accepted_at_check'),
    sa.CheckConstraint("status IN ('draft', 'sent', 'accepted', 'declined', 'expired', 'superseded')", name='quotes_status_check'),
    sa.CheckConstraint("status NOT IN ('sent', 'accepted') OR sent_at IS NOT NULL", name='quotes_sent_at_check'),
    sa.CheckConstraint('discount_percent BETWEEN 0 AND 100', name='quotes_discount_check'),
    sa.CheckConstraint('guest_count > 0', name='quotes_guest_count_check'),
    sa.CheckConstraint('subtotal_amount >= 0 AND discount_amount >= 0 AND service_charge_amount >= 0 AND gratuity_amount >= 0 AND tax_amount >= 0 AND total_amount >= 0 AND per_guest_amount >= 0', name='quotes_amounts_check'),
    sa.ForeignKeyConstraint(['created_by'], ['user_data.user_id'], name='quotes_created_by_fkey', ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['invoice_id'], ['invoices.invoice_id'], name='quotes_invoice_id_fkey', ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['org_id', 'pricing_model_id', 'tier_id'], ['pricing_tiers.org_id', 'pricing_tiers.pricing_model_id', 'pricing_tiers.id'], name='quotes_tier_fkey', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['org_id', 'pricing_model_id'], ['pricing_models.org_id', 'pricing_models.id'], name='quotes_model_org_fkey', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.org_id'], name='quotes_org_id_fkey', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['subproject_id'], ['subprojects.subproject_id'], name='quotes_subproject_id_fkey', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_quotes_subproject_id', 'quotes', ['subproject_id'], unique=False)
    op.create_index('quotes_invoice_key', 'quotes', ['invoice_id'], unique=True, postgresql_where=sa.text('invoice_id IS NOT NULL'))
    op.create_index('quotes_org_status', 'quotes', ['org_id', 'status'], unique=False)
    op.create_index('quotes_pricing_model', 'quotes', ['pricing_model_id'], unique=False)

    op.create_table('quote_lines',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('quote_id', sa.UUID(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('kind', sa.String(), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('description', sa.String(), nullable=True),
    sa.Column('charge_unit', sa.String(), nullable=False),
    sa.Column('quantity', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('unit_price', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('line_total', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('source_table', sa.String(length=63), nullable=True),
    sa.Column('source_id', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("charge_unit IN ('guest', 'event', 'item', 'hour', 'tray')", name='quote_lines_unit_check'),
    sa.CheckConstraint("kind <> 'discount' OR line_total <= 0", name='quote_lines_discount_check'),
    sa.CheckConstraint("kind = 'discount' OR (unit_price >= 0 AND line_total >= 0)", name='quote_lines_amount_check'),
    sa.CheckConstraint("kind IN ('base', 'tier_addition', 'dish_surcharge', 'adjustment', 'live_station', 'rate_card', 'equipment', 'service_charge', 'gratuity', 'tax', 'discount', 'custom')", name='quote_lines_kind_check'),
    sa.CheckConstraint('length(trim(name)) > 0', name='quote_lines_name_check'),
    sa.CheckConstraint('position >= 0', name='quote_lines_position_check'),
    sa.CheckConstraint('quantity > 0', name='quote_lines_quantity_check'),
    sa.ForeignKeyConstraint(['quote_id'], ['quotes.id'], name='quote_lines_quote_id_fkey', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('quote_id', 'position', name='quote_lines_quote_position_key')
    )
    op.create_index('ix_quote_lines_quote_id', 'quote_lines', ['quote_id'], unique=False)

    op.create_table('quote_dishes',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('quote_id', sa.UUID(), nullable=False),
    sa.Column('menu_item_id', sa.UUID(), nullable=True),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('course', sa.String(length=50), nullable=False),
    sa.Column('dish_name', sa.String(), nullable=False),
    sa.Column('price_weight', sa.String(), nullable=True),
    sa.Column('surcharge_per_guest', sa.Numeric(precision=12, scale=2), server_default='0', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("price_weight IN ('light', 'standard', 'premium')", name='quote_dishes_price_weight_check'),
    sa.CheckConstraint('length(trim(course)) > 0 AND length(trim(dish_name)) > 0', name='quote_dishes_text_check'),
    sa.CheckConstraint('position >= 0', name='quote_dishes_position_check'),
    sa.CheckConstraint('surcharge_per_guest >= 0', name='quote_dishes_surcharge_check'),
    sa.ForeignKeyConstraint(['menu_item_id'], ['menu_items.id'], name='quote_dishes_menu_item_id_fkey', ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['quote_id'], ['quotes.id'], name='quote_dishes_quote_id_fkey', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('quote_id', 'position', name='quote_dishes_quote_position_key')
    )
    op.create_index('ix_quote_dishes_menu_item_id', 'quote_dishes', ['menu_item_id'], unique=False)
    op.create_index('ix_quote_dishes_quote_id', 'quote_dishes', ['quote_id'], unique=False)


def downgrade() -> None:
    # Pricing rows hang off models, and live stations off organizations; the
    # old shape has nowhere to put that link, so the tables must be empty.
    _require_empty(['quotes', 'pricing_tiers', *_CONFIG_TABLES, 'live_stations'])

    op.drop_table('quote_dishes')
    op.drop_table('quote_lines')
    op.drop_table('quotes')

    op.drop_constraint('live_stations_name_check', 'live_stations', type_='check')
    op.drop_constraint('live_stations_min_guests_check', 'live_stations', type_='check')
    op.drop_constraint('live_stations_price_check', 'live_stations', type_='check')
    op.drop_constraint('live_stations_veg_nonveg_check', 'live_stations', type_='check')
    op.drop_index('live_stations_org_name_key', table_name='live_stations')
    op.drop_index('ix_live_stations_org_id', table_name='live_stations')
    op.drop_constraint('live_stations_org_id_fkey', 'live_stations', type_='foreignkey')
    op.alter_column('live_stations', 'equipment_needed',
               existing_type=postgresql.ARRAY(sa.VARCHAR()),
               nullable=True,
               existing_server_default=sa.text("'{}'::character varying[]"))
    op.alter_column('live_stations', 'price_per_person',
               existing_type=sa.Numeric(precision=12, scale=2),
               type_=sa.NUMERIC(precision=8, scale=2),
               existing_nullable=False)
    for column in ['updated_at', 'created_at', 'active', 'min_guests', 'description', 'org_id']:
        op.drop_column('live_stations', column)

    op.drop_table('pricing_policies')
    op.drop_table('pricing_tier_courses')

    op.drop_constraint('pricing_adjustments_dish_or_class_check', 'pricing_adjustments', type_='check')
    op.drop_constraint('pricing_adjustments_price_weight_check', 'pricing_adjustments', type_='check')
    op.drop_column('pricing_adjustments', 'price_weight')

    for table in ['pricing_adjustments', 'pricing_tier_additions']:
        op.drop_constraint(f'{table}_tier_fkey', table, type_='foreignkey')
        op.drop_index(f'{table}_model_tier', table_name=table)
        op.create_index(f'{table}_org_tier', table, ['org_id', 'tier_id'], unique=False)
    for table in _CONFIG_TABLES:
        op.drop_constraint(f'{table}_model_org_fkey', table, type_='foreignkey')
        op.drop_index(f'{table}_model_lookup', table_name=table)
        op.create_index(f'{table}_org_lookup', table, ['org_id', 'active', 'currency', 'effective_from'], unique=False)
        op.drop_column(table, 'pricing_model_id')

    op.drop_index('pricing_tiers_one_active_base', table_name='pricing_tiers')
    op.drop_index('pricing_tiers_model_name_key', table_name='pricing_tiers')
    op.drop_constraint('pricing_tiers_model_position_key', 'pricing_tiers', type_='unique')
    op.drop_constraint('pricing_tiers_org_model_id_key', 'pricing_tiers', type_='unique')
    op.drop_constraint('pricing_tiers_model_org_fkey', 'pricing_tiers', type_='foreignkey')
    op.drop_column('pricing_tiers', 'pricing_model_id')
    op.create_index('pricing_tiers_one_active_base', 'pricing_tiers', ['org_id'], unique=True, postgresql_where=sa.text('is_base AND active'))
    op.create_index('pricing_tiers_org_name_key', 'pricing_tiers', ['org_id', sa.literal_column('lower(name)')], unique=True)
    op.create_unique_constraint('pricing_tiers_org_position_key', 'pricing_tiers', ['org_id', 'position'])
    op.create_unique_constraint('pricing_tiers_org_id_id_key', 'pricing_tiers', ['org_id', 'id'])
    for table in ['pricing_adjustments', 'pricing_tier_additions']:
        op.create_foreign_key(f'{table}_tier_org_fkey', table, 'pricing_tiers', ['org_id', 'tier_id'], ['org_id', 'id'], ondelete='RESTRICT')

    op.drop_index('pricing_models_one_published', table_name='pricing_models')
    op.drop_table('pricing_models')
