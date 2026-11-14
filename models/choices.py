"""Fixed value lists for subproject fields.

Each list is defined once here and used by both the model (as a CHECK
constraint) and the schemas (as the field type). To add or rename a value,
change it here and add a migration that drops and recreates the matching
constraint, updating existing rows for a rename. "Other" covers anything
the list doesn't name.
"""
from enum import StrEnum


class Religion(StrEnum):
    HINDU = "Hindu"
    MUSLIM = "Muslim"
    CHRISTIAN = "Christian"


class ServiceStyle(StrEnum):
    BUFFET = "Buffet"
    PLATED = "Plated"
    FAMILY_STYLE = "Family Style"
    LIVE_STATIONS = "Live Stations"
    BUTLER_PASSED = "Butler Passed"
    OTHER = "Other"


class Venue(StrEnum):
    HOTEL = "Hotel"
    COUNTRY_CLUB = "Country Club"
    MUSEUM = "Museum"
    PARTY_HALL = "Party Hall"
    HOME = "Home"
    OUTDOOR = "Outdoor"
    OTHER = "Other"


class EventType(StrEnum):
    BREAKFAST = "Breakfast"
    WEDDING_LUNCH = "Wedding Lunch"
    WEDDING_DINNER = "Wedding Dinner"
    ANNIVERSARY = "Anniversary"
    BIRTHDAY = "Birthday"
    COCKTAIL_HOUR = "Cocktail Hour"
    MEHENDI = "Mehendi"
    HALDI = "Haldi"
    CEREMONY_REFRESHMENTS = "Ceremony Refreshments"
    VIDAI = "Vidai"
    WELCOME_DINNER = "Welcome Dinner"
    WELCOME_LUNCH = "Welcome Lunch"
    BAARAT = "Baarat"
    WALIMA = "Walima"
    GRADUATION = "Graduation"
    HOUSEWARMING = "Housewarming"
    HIGH_TEA = "High Tea"
    OTHER = "Other"


class Diet(StrEnum):
    """Dietary needs an event caters for; an event can have several."""

    VEGAN = "Vegan"
    VEGETARIAN = "Vegetarian"
    JAIN = "Jain"
    HALAL = "Halal"
    NON_VEGETARIAN = "Non-Vegetarian"
    EGGETARIAN = "Eggetarian"
    KOSHER = "Kosher"
    GLUTEN_FREE = "Gluten-Free"
    DAIRY_FREE = "Dairy-Free"
    OTHER = "Other"



class PricingUnit(StrEnum):
    """What a rate card price is per."""

    GUEST = "guest"
    HOUR = "hour"
    EVENT = "event"
    TRAY = "tray"


class PriceWeight(StrEnum):
    """A dish's cost class (menu_items.price_weight). Pricing uses it to decide
    which dishes a tier's base price covers and which carry a surcharge."""

    LIGHT = "light"
    STANDARD = "standard"
    PREMIUM = "premium"


class PricingMethod(StrEnum):
    """How a caterer prices. Each method is a calculator in code with its own
    configuration tables; a caterer picks one per pricing model."""

    TIERED_PER_GUEST = "tiered_per_guest"


class PricingModelStatus(StrEnum):
    """Only a draft is edited; a quote uses the published version."""

    DRAFT = "draft"
    PUBLISHED = "published"
    RETIRED = "retired"


class TaxMode(StrEnum):
    PER_DISH_CATEGORY = "per_dish_category"  # each dish's tax_categories rate
    FLAT_RATE = "flat_rate"  # pricing_policies.flat_tax_percent on the whole quote
    NONE = "none"


class LiveStationDiet(StrEnum):
    VEG = "veg"
    NONVEG = "nonveg"
    BOTH = "both"


class MealPeriod(StrEnum):
    """When in the day a live station is offered (live_stations.meal_periods)."""

    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"


class QuoteStatus(StrEnum):
    DRAFT = "draft"
    SENT = "sent"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    EXPIRED = "expired"
    SUPERSEDED = "superseded"


class QuoteLineKind(StrEnum):
    BASE = "base"
    TIER_ADDITION = "tier_addition"
    DISH_SURCHARGE = "dish_surcharge"
    ADJUSTMENT = "adjustment"
    LIVE_STATION = "live_station"
    RATE_CARD = "rate_card"
    EQUIPMENT = "equipment"
    SERVICE_CHARGE = "service_charge"
    GRATUITY = "gratuity"
    TAX = "tax"
    DISCOUNT = "discount"
    CUSTOM = "custom"


class QuoteLineUnit(StrEnum):
    GUEST = "guest"
    EVENT = "event"
    ITEM = "item"
    HOUR = "hour"
    TRAY = "tray"


def check_in(column: str, choices: type[StrEnum]) -> str:
    """SQL for a CHECK constraint limiting `column` to the enum's values."""
    values = ", ".join(f"'{choice.value}'" for choice in choices)
    return f"{column} IN ({values})"


def check_all_in(column: str, choices: type[StrEnum]) -> str:
    """SQL for a CHECK constraint limiting every element of the array
    `column` to the enum's values (an empty array passes)."""
    values = ", ".join(f"'{choice.value}'" for choice in choices)
    return f"{column} <@ ARRAY[{values}]::varchar[]"
