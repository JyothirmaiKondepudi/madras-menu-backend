"""Standalone model tests; avoids the app suite's destructive DB fixtures.

DATABASE_URL=postgresql+psycopg2://... PRICING_TEST_DATABASE_URL=postgresql+psycopg2://... \
    python -m unittest discover -s tests/pricing_model -v

Database tests use a unique disposable schema, never existing app tables.
"""
import importlib.util
import os
from datetime import date
from decimal import Decimal
from pathlib import Path
import unittest
from uuid import uuid4

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg2://postgres@localhost/postgres")

from alembic.migration import MigrationContext
from alembic.operations import Operations
from pydantic import ValidationError
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from models import PricingTier, PricingBaseRate, PricingAdjustment, PricingTierAddition
from schemas.pricing import (
    PricingTierCreate, PricingBaseRateCreate, PricingAdjustmentCreate,
    PricingTierAdditionCreate,
)


class InputTests(unittest.TestCase):
    def base(self, **changes):
        return dict(name="Wedding base", inclusions="Standard package",
                    pricePerPerson="40.00", currency="USD", effectiveFrom="2026-11-01", **changes)

    def test_decimal_and_wildcards(self):
        value = PricingBaseRateCreate(**self.base())
        self.assertEqual(value.pricePerPerson, Decimal("40.00"))
        self.assertIsNone(value.eventType)

    def test_invalid_ranges(self):
        for changes in [dict(minGuests=100, maxGuests=50),
                        dict(effectiveUntil="2026-11-01"), dict(minGuests=0)]:
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                PricingBaseRateCreate(**self.base(**changes))

    def test_invalid_money(self):
        for amount in ["-1", "1.001", "NaN", "Infinity"]:
            payload = self.base()
            payload["pricePerPerson"] = amount
            with self.subTest(amount=amount), self.assertRaises(ValidationError):
                PricingBaseRateCreate(**payload)

    def test_no_caller_supplied_org(self):
        with self.assertRaises(ValidationError):
            PricingTierCreate(name="Elegant", position=0, orgId=uuid4())

    def test_controlled_conditions_and_units(self):
        payload = dict(name="Extra", currency="USD", effectiveFrom=date.today(), amount="5")
        for changes in [dict(chargeUnit="percentage"), dict(chargeUnit="guest", eventType="Typo")]:
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                PricingAdjustmentCreate(**payload, **changes)

    def test_addition_requires_tier_and_description(self):
        with self.assertRaises(ValidationError):
            PricingTierAdditionCreate(name="Extra starter", amount="5", chargeUnit="guest",
                                      currency="USD", effectiveFrom=date.today())

    def test_blank_tier_name(self):
        with self.assertRaises(ValidationError):
            PricingTierCreate(name="  ", position=0)


@unittest.skipUnless(os.environ.get("PRICING_TEST_DATABASE_URL"), "Set PRICING_TEST_DATABASE_URL for PostgreSQL checks")
class DatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(os.environ["PRICING_TEST_DATABASE_URL"])

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()

    def setUp(self):
        self.connection = self.engine.connect()
        self.transaction = self.connection.begin()
        self.schema = "pricing_test_" + uuid4().hex
        self.connection.execute(text(f'CREATE SCHEMA "{self.schema}"'))
        self.connection.execute(text(f'SET LOCAL search_path TO "{self.schema}"'))
        # Minimal external identities; this migration does not own these tables.
        self.connection.execute(text("CREATE TABLE organizations (org_id uuid PRIMARY KEY)"))
        self.connection.execute(text("CREATE TABLE menu_items (id uuid PRIMARY KEY)"))
        self.connection.execute(text("CREATE TABLE price_tiers (id text PRIMARY KEY)"))
        self.connection.execute(text("INSERT INTO price_tiers VALUES ('legacy')"))
        path = Path(__file__).resolve().parents[2] / "alembic/versions/a7b83c91d204_organization_pricing.py"
        spec = importlib.util.spec_from_file_location("pricing_migration", path)
        self.migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.migration)
        self.operations = Operations(MigrationContext.configure(self.connection))
        with self.operations.context(MigrationContext.configure(self.connection)):
            self.migration.upgrade()
        self.org, self.other_org, self.tier = uuid4(), uuid4(), uuid4()
        self.connection.execute(text("INSERT INTO organizations VALUES (:a), (:b)"), {"a": self.org, "b": self.other_org})
        self.insert(PricingTier, id=self.tier, orgId=self.org, name="Elegant", position=0, isBase=True)

    def tearDown(self):
        self.transaction.rollback()
        self.connection.close()

    def insert(self, model, **values):
        from sqlalchemy import insert
        mapped = {getattr(model, key).property.columns[0].name: value for key, value in values.items()}
        self.connection.execute(insert(model.__table__).values(**mapped))

    def addition(self, **changes):
        values = dict(orgId=self.org, tierId=self.tier, name="Starter", description="Extra starter",
                      amount=Decimal("5"), chargeUnit="guest", currency="USD", effectiveFrom=date(2026, 11, 1))
        values.update(changes)
        return values

    def rejected(self, model, **values):
        with self.assertRaises(IntegrityError):
            with self.connection.begin_nested():
                self.insert(model, **values)

    def test_cross_org_links_rejected(self):
        self.rejected(PricingTierAddition, **self.addition(orgId=self.other_org))
        values = self.addition(orgId=self.other_org)
        del values["description"]
        self.rejected(PricingAdjustment, **values)

    def test_orgs_can_have_same_tier_names_and_positions(self):
        self.insert(PricingTier, orgId=self.other_org, name="Elegant", position=0, isBase=True)
        self.rejected(PricingTier, orgId=self.org, name="elegant", position=1)
        self.rejected(PricingTier, orgId=self.org, name="Other", position=0)

    def test_only_one_active_base_per_org(self):
        self.rejected(PricingTier, orgId=self.org, name="Second base", position=1, isBase=True)
        self.insert(PricingTier, orgId=self.org, name="Retired base", position=2, isBase=True, active=False)

    def test_database_validates_ranges_amounts_units_and_currency(self):
        for changes in [dict(minGuests=100, maxGuests=20), dict(effectiveUntil=date(2026,11,1)),
                        dict(amount=-1), dict(chargeUnit="invalid"), dict(currency="usd"),
                        dict(eventType="Unknown"), dict(serviceStyle="Unknown"), dict(name=" ")]:
            with self.subTest(changes=changes):
                self.rejected(PricingTierAddition, **self.addition(**changes))

    def test_distinct_org_prices_and_optional_dish(self):
        dish = uuid4()
        self.connection.execute(text("INSERT INTO menu_items VALUES (:id)"), {"id": dish})
        for org, amount in [(self.org, "100.00"), (self.other_org, "120.00")]:
            self.insert(PricingAdjustment, orgId=org, menuItemId=dish, name="Dish upgrade",
                        amount=Decimal(amount), chargeUnit="guest", currency="USD", effectiveFrom=date.today())
        prices = self.connection.execute(text("SELECT amount FROM pricing_adjustments ORDER BY amount")).scalars().all()
        self.assertEqual(prices, [Decimal("100.00"), Decimal("120.00")])

    def test_model_and_migration_columns_match(self):
        inspector = inspect(self.connection)
        for model in [PricingTier, PricingBaseRate, PricingAdjustment, PricingTierAddition]:
            actual = {c["name"]: c for c in inspector.get_columns(model.__tablename__, schema=self.schema)}
            self.assertEqual(set(actual), set(model.__table__.columns.keys()))
            for column in model.__table__.columns:
                self.assertEqual(actual[column.name]["nullable"], column.nullable)

    def test_downgrade_preserves_legacy_table(self):
        with self.operations.context(MigrationContext.configure(self.connection)):
            self.migration.downgrade()
        self.assertEqual(self.connection.execute(text("SELECT id FROM price_tiers")).scalar_one(), "legacy")
        self.assertNotIn("pricing_tiers", inspect(self.connection).get_table_names(schema=self.schema))


if __name__ == "__main__":
    unittest.main()
