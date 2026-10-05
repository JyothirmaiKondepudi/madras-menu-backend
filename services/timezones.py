"""Event timezone rules.

Event times (project start/end, subproject date) belong to the venue, so each
one is read in its *effective* timezone: the project's own timezone if set,
otherwise its organization's. A time sent without an offset is taken as local
time there; a time sent with an offset is used as given. Everything is stored
as an exact instant (timestamptz).
"""
from datetime import datetime
from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

from pydantic import AfterValidator

DEFAULT_TIMEZONE = "America/New_York"


def validate_timezone(name: str) -> str:
    """Raises ValueError for anything that isn't an IANA timezone name."""
    if name not in available_timezones():
        raise ValueError(f"unknown timezone {name!r}; use an IANA name like 'America/New_York'")
    try:
        ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"unknown timezone {name!r}") from exc
    return name


def effective_timezone(project) -> str:
    return project.projectTimezone or project.organization.orgTimezone


def to_instant(value: datetime | None, timezone: str) -> datetime | None:
    """Attach the venue timezone to a naive time; leave aware times alone."""
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=ZoneInfo(timezone))


def to_local(value: datetime | None, timezone: str) -> datetime | None:
    return value.astimezone(ZoneInfo(timezone)) if value is not None else None


# a request field holding an IANA timezone name; invalid names get a 422
IanaTimezone = Annotated[str, AfterValidator(validate_timezone)]
