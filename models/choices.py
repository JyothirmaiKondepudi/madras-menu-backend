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


def check_in(column: str, choices: type[StrEnum]) -> str:
    """SQL for a CHECK constraint limiting `column` to the enum's values."""
    values = ", ".join(f"'{choice.value}'" for choice in choices)
    return f"{column} IN ({values})"


def check_all_in(column: str, choices: type[StrEnum]) -> str:
    """SQL for a CHECK constraint limiting every element of the array
    `column` to the enum's values (an empty array passes)."""
    values = ", ".join(f"'{choice.value}'" for choice in choices)
    return f"{column} <@ ARRAY[{values}]::varchar[]"
