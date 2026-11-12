"""Pricing models, their configuration, live stations and quotes.

Input checks run without a database. Database checks insert through the ORM
into the test database (built with create_all, like the rest of the suite)
and prove the constraints the pricing calculator will rely on.
"""
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from models import (
    LiveStation, Organization, PricingAdjustment, PricingBaseRate, PricingModel,
    PricingPolicy, PricingTier, PricingTierAddition, PricingTierCourse, Quote,
    QuoteDish, QuoteLine,
)
from schemas.pricing import (
    LiveStationCreate, PricingAdjustmentCreate, PricingBaseRateCreate,
    PricingModelCreate, PricingPolicyCreate, PricingTierAdditionCreate,
    PricingTierCourseCreate, PricingTierCreate,
)

NOW = datetime(2026, 11, 1, tzinfo=timezone.utc)


# --- input validation (no database) -----------------------------------------

def _base_rate(**changes):
    return dict(name="Wedding base", inclusions="Standard package", pricePerPerson="40.00",
                currency="USD", effectiveFrom="2026-11-01", **changes)


def test_base_rate_decimal_and_wildcards():
    value = PricingBaseRateCreate(**_base_rate())
    assert value.pricePerPerson == Decimal("40.00")
    assert value.eventType is None


@pytest.mark.parametrize("changes", [
    dict(minGuests=100, maxGuests=50), dict(effectiveUntil="2026-11-01"), dict(minGuests=0),
    dict(pricePerPerson="-1"), dict(pricePerPerson="1.001"), dict(pricePerPerson="NaN"),
])
def test_base_rate_rejects_bad_ranges_and_money(changes):
    payload = _base_rate()
    payload.update(changes)
    with pytest.raises(ValidationError):
        PricingBaseRateCreate(**payload)


def test_inputs_never_take_an_org_id():
    with pytest.raises(ValidationError):
        PricingTierCreate(name="Elegant", position=0, orgId=uuid4())
    with pytest.raises(ValidationError):
        LiveStationCreate(name="Dosa", region="south_indian", vegNonveg="veg", pricePerPerson="8", orgId=uuid4())


def test_tier_name_cannot_be_blank():
    with pytest.raises(ValidationError):
        PricingTierCreate(name="  ", position=0)


def test_model_defaults_to_tiered_per_guest():
    assert PricingModelCreate(name="2027 rates").method == "tiered_per_guest"
    with pytest.raises(ValidationError):
        PricingModelCreate(name="2027 rates", method="per_tray")


@pytest.mark.parametrize("changes", [dict(chargeUnit="percentage"), dict(eventType="Typo"),
                                     dict(priceWeight="gold"), dict(priceWeight="premium", menuItemId=uuid4())])
def test_adjustment_rejects_bad_units_conditions_and_targets(changes):
    payload = dict(name="Extra", currency="USD", effectiveFrom=date.today(), amount="5", chargeUnit="guest")
    payload.update(changes)
    with pytest.raises(ValidationError):
        PricingAdjustmentCreate(**payload)


def test_adjustment_accepts_a_dish_class():
    value = PricingAdjustmentCreate(name="Premium dish", currency="USD", effectiveFrom=date.today(),
                                    amount="15", chargeUnit="guest", priceWeight="premium")
    assert value.priceWeight == "premium"


def test_addition_requires_tier_and_description():
    with pytest.raises(ValidationError):
        PricingTierAdditionCreate(name="Extra starter", amount="5", chargeUnit="guest",
                                  currency="USD", effectiveFrom=date.today())


@pytest.mark.parametrize("changes", [dict(dishCount=0), dict(includedPriceWeights=["gold"]),
                                     dict(includedPriceWeights=["light", "light"]), dict(course=" ")])
def test_tier_course_rejects_bad_slots(changes):
    payload = dict(tierId=uuid4(), course="main", dishCount=3, includedPriceWeights=["light", "standard"])
    payload.update(changes)
    with pytest.raises(ValidationError):
        PricingTierCourseCreate(**payload)


def test_policy_flat_tax_only_with_flat_rate_mode():
    assert PricingPolicyCreate(currency="USD", taxMode="flat_rate", flatTaxPercent="8.25").flatTaxPercent == Decimal("8.25")
    for payload in [dict(taxMode="flat_rate"), dict(taxMode="none", flatTaxPercent="5"),
                    dict(serviceChargePercent="101"), dict(roundingIncrement="0")]:
        with pytest.raises(ValidationError):
            PricingPolicyCreate(currency="USD", **payload)


def test_live_station_diet_values():
    with pytest.raises(ValidationError):
        LiveStationCreate(name="Dosa", region="south_indian", vegNonveg="vegetarian", pricePerPerson="8")


# --- database constraints ---------------------------------------------------

@pytest.fixture()
def db(engine):
    session = sessionmaker(bind=engine)()
    yield session
    session.rollback()
    session.close()


def _org(db, name="Madras Catering"):
    org = Organization(orgName=name, orgEmail=f"{uuid4().hex}@example.com", orgDisabled=False)
    db.add(org)
    db.flush()
    return org.orgId


def _model(db, org_id, version=1, status="draft"):
    model = PricingModel(orgId=org_id, method="tiered_per_guest", version=version, status=status,
                         name=f"Rates v{version}", publishedAt=NOW if status != "draft" else None)
    db.add(model)
    db.flush()
    return model


def _tier(db, model, name="Elegant", position=0, is_base=True):
    tier = PricingTier(orgId=model.orgId, pricingModelId=model.id, name=name, position=position, isBase=is_base)
    db.add(tier)
    db.flush()
    return tier


def _conditions(model):
    return dict(orgId=model.orgId, pricingModelId=model.id, currency="USD", effectiveFrom=date(2026, 11, 1))


def _rejected(db, constraint, row):
    """The insert fails, and on the constraint this test is about."""
    nested = db.begin_nested()
    db.add(row)
    with pytest.raises(IntegrityError) as error:
        db.flush()
    nested.rollback()
    assert error.value.orig.diag.constraint_name == constraint


@pytest.fixture()
def madras(db):
    org = _org(db)
    model = _model(db, org)
    elegant = _tier(db, model)
    return org, model, elegant


def test_versions_are_unique_and_only_one_is_published(db):
    org = _org(db)
    _model(db, org, version=1, status="published")
    _rejected(db, "pricing_models_org_version_key", PricingModel(orgId=org, method="tiered_per_guest", version=1, name="Copy"))
    _rejected(db, "pricing_models_one_published", PricingModel(orgId=org, method="tiered_per_guest", version=2, status="published",
                               publishedAt=NOW, name="Second live"))
    _rejected(db, "pricing_models_published_at_check", PricingModel(orgId=org, method="tiered_per_guest", version=3, status="published", name="No date"))
    _model(db, org, version=2)  # a draft next to the published one is fine
    _model(db, _org(db, "Other caterer"), version=1, status="published")  # other orgs have their own


def test_tier_rules_apply_per_model(db, madras):
    org, model, _ = madras
    _rejected(db, "pricing_tiers_model_name_key", PricingTier(orgId=org, pricingModelId=model.id, name="ELEGANT", position=1))
    _rejected(db, "pricing_tiers_model_position_key", PricingTier(orgId=org, pricingModelId=model.id, name="Premium", position=0))
    _rejected(db, "pricing_tiers_one_active_base", PricingTier(orgId=org, pricingModelId=model.id, name="Second base", position=1, isBase=True))
    next_version = _model(db, org, version=2)
    _tier(db, next_version, name="Elegant", position=0, is_base=True)  # same names in a new version


def test_links_cannot_cross_models_or_organizations(db, madras):
    org, model, elegant = madras
    other_version = _model(db, org, version=2)
    _rejected(db, "pricing_tier_additions_tier_fkey", PricingTierAddition(**_conditions(other_version), tierId=elegant.id, name="Starter",
                                      description="Extra starter", amount=Decimal("5"), chargeUnit="guest"))
    other_org_model = _model(db, _org(db, "Other caterer"))
    _rejected(db, "pricing_tiers_model_org_fkey", PricingTier(orgId=org, pricingModelId=other_org_model.id, name="Stolen", position=5))
    _rejected(db, "pricing_tier_courses_tier_fkey", PricingTierCourse(orgId=org, pricingModelId=other_version.id, tierId=elegant.id,
                                    course="main", dishCount=3))


def test_tier_courses(db, madras):
    org, model, elegant = madras
    db.add(PricingTierCourse(orgId=org, pricingModelId=model.id, tierId=elegant.id, course="main",
                             dishCount=3, includedPriceWeights=["light", "standard"]))
    db.flush()
    _rejected(db, "pricing_tier_courses_tier_course_key", PricingTierCourse(orgId=org, pricingModelId=model.id, tierId=elegant.id, course="Main", dishCount=2))
    _rejected(db, "pricing_tier_courses_price_weights_check", PricingTierCourse(orgId=org, pricingModelId=model.id, tierId=elegant.id, course="dessert",
                                    dishCount=1, includedPriceWeights=["gold"]))
    _rejected(db, "pricing_tier_courses_dish_count_check", PricingTierCourse(orgId=org, pricingModelId=model.id, tierId=elegant.id, course="bread", dishCount=0))


def test_adjustment_targets_a_dish_or_a_class(db, madras, test_menu_item):
    _, model, elegant = madras
    db.add(PricingAdjustment(**_conditions(model), tierId=elegant.id, name="Premium dish", priceWeight="premium",
                             amount=Decimal("15"), chargeUnit="guest"))
    db.flush()
    _rejected(db, "pricing_adjustments_dish_or_class_check", PricingAdjustment(**_conditions(model), name="Both", priceWeight="premium",
                                    menuItemId=test_menu_item["id"], amount=Decimal("1"), chargeUnit="guest"))
    _rejected(db, "pricing_adjustments_price_weight_check", PricingAdjustment(**_conditions(model), name="Bad class", priceWeight="gold",
                                    amount=Decimal("1"), chargeUnit="guest"))


def test_one_policy_per_model_with_consistent_tax(db, madras):
    org, model, _ = madras
    db.add(PricingPolicy(orgId=org, pricingModelId=model.id, currency="USD", serviceChargePercent=Decimal("18")))
    db.flush()
    _rejected(db, "pricing_policies_pricing_model_id_key", PricingPolicy(orgId=org, pricingModelId=model.id, currency="USD"))
    other = _model(db, org, version=2)
    _rejected(db, "pricing_policies_flat_tax_check", PricingPolicy(orgId=org, pricingModelId=other.id, currency="USD", taxMode="flat_rate"))
    _rejected(db, "pricing_policies_percent_check", PricingPolicy(orgId=org, pricingModelId=other.id, currency="USD", serviceChargePercent=Decimal("120")))


def test_deleting_a_draft_model_removes_its_configuration(db, madras):
    org, model, elegant = madras
    db.add_all([
        PricingTierCourse(orgId=org, pricingModelId=model.id, tierId=elegant.id, course="main", dishCount=3),
        PricingBaseRate(**_conditions(model), name="Base", pricePerPerson=Decimal("40"), inclusions="Base package"),
        PricingPolicy(orgId=org, pricingModelId=model.id, currency="USD"),
    ])
    db.flush()
    db.delete(model)
    db.flush()
    db.expire_all()
    for table in [PricingTier, PricingTierCourse, PricingBaseRate, PricingPolicy]:
        assert db.query(table).count() == 0


def test_live_stations_belong_to_a_caterer(db):
    org, other = _org(db), _org(db, "Other caterer")
    station = dict(region="south_indian", vegNonveg="veg", pricePerPerson=Decimal("8.50"))
    db.add(LiveStation(orgId=org, name="Dosa Station", **station))
    db.add(LiveStation(orgId=other, name="Dosa Station", **station))
    db.flush()
    _rejected(db, "live_stations_org_name_key", LiveStation(orgId=org, name="dosa station", **station))
    _rejected(db, "live_stations_veg_nonveg_check", LiveStation(orgId=org, name="Chaat", region="north_indian", vegNonveg="vegetarian",
                              pricePerPerson=Decimal("5")))
    _rejected(db, "live_stations_min_guests_check", LiveStation(orgId=org, name="Pasta", region="italian", vegNonveg="veg",
                              pricePerPerson=Decimal("5"), minGuests=0))


@pytest.fixture()
def quote_setup(db, client, test_project, vendor_auth_headers, test_vendor_login):
    resp = client.post("/subprojects", json={
        "subprojectName": "Sangeet", "projectAssociatedTo": test_project["projectId"],
        "cuisine": ["South Indian"], "religion": "Hindu", "subprojectDate": "2026-12-01T19:00:00",
        "guestCount": 150, "subprojectType": "Buffet", "subprojectVenue": "Hotel",
        "subprojectEvent": "Wedding Dinner",
    }, headers=vendor_auth_headers)
    assert resp.status_code == 200, resp.text
    org = test_vendor_login["userOrg"]
    model = _model(db, org, status="published")
    tier = _tier(db, model)
    return dict(orgId=org, subprojectId=resp.json()["subprojectId"], pricingModelId=model.id,
                tierId=tier.id, guestCount=150, currency="USD"), model


def test_quote_with_frozen_lines_and_dishes(db, quote_setup, test_menu_item):
    values, _ = quote_setup
    quote = Quote(**values, subtotalAmount=Decimal("6000"), discountAmount=Decimal("300"),
                  totalAmount=Decimal("5700"), perGuestAmount=Decimal("38"))
    db.add(quote)
    db.flush()
    db.add_all([
        QuoteLine(quoteId=quote.id, position=0, kind="base", name="Elegant package", chargeUnit="guest",
                  quantity=150, unitPrice=Decimal("40"), lineTotal=Decimal("6000")),
        QuoteLine(quoteId=quote.id, position=1, kind="discount", name="5% off", chargeUnit="event",
                  quantity=1, unitPrice=Decimal("-300"), lineTotal=Decimal("-300")),
        QuoteDish(quoteId=quote.id, position=0, menuItemId=test_menu_item["id"], course="main",
                  dishName="Test Dish", priceWeight="standard"),
    ])
    db.flush()
    _rejected(db, "quote_lines_amount_check", QuoteLine(quoteId=quote.id, position=2, kind="base", name="Negative", chargeUnit="guest",
                            quantity=1, unitPrice=Decimal("-1"), lineTotal=Decimal("-1")))
    _rejected(db, "quote_lines_discount_check", QuoteLine(quoteId=quote.id, position=2, kind="discount", name="Positive discount",
                            chargeUnit="event", quantity=1, unitPrice=Decimal("5"), lineTotal=Decimal("5")))
    _rejected(db, "quote_lines_quote_position_key", QuoteLine(quoteId=quote.id, position=0, kind="custom", name="Same position",
                            chargeUnit="event", quantity=1, unitPrice=Decimal("5"), lineTotal=Decimal("5")))
    db.delete(quote)
    db.flush()
    assert db.query(QuoteLine).count() == 0 and db.query(QuoteDish).count() == 0


def test_quote_status_and_pricing_version_rules(db, quote_setup):
    values, model = quote_setup
    _rejected(db, "quotes_sent_at_check", Quote(**values, status="sent"))  # sent needs sent_at
    _rejected(db, "quotes_accepted_at_check", Quote(**values, status="accepted", sentAt=NOW))  # accepted needs accepted_at
    _rejected(db, "quotes_tier_fkey", Quote(**{**values, "tierId": _tier(db, _model(db, values["orgId"], version=2)).id}))
    db.add(Quote(**values, status="accepted", sentAt=NOW, acceptedAt=NOW))
    db.flush()
    nested = db.begin_nested()
    db.delete(model)
    with pytest.raises(IntegrityError):  # a version a quote used can't be deleted
        db.flush()
    nested.rollback()
