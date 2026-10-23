import re
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, HttpUrl, TypeAdapter, field_validator
from uuid import UUID
from datetime import datetime

from services.timezones import IanaTimezone


_HTTP_URL = TypeAdapter(HttpUrl)


def _http_url(value: str) -> str:
    # validated as an http(s) URL, stored exactly as given
    _HTTP_URL.validate_python(value)
    return value


def _ein(value: str) -> str:
    # 9 digits, with or without the dash; stored as 12-3456789
    digits = re.sub(r"[\s-]", "", value)
    if not re.fullmatch(r"\d{9}", digits):
        raise ValueError("an EIN is 9 digits, like 12-3456789")
    return f"{digits[:2]}-{digits[2:]}"


def _country(value: str) -> str:
    code = value.strip().upper()
    if not re.fullmatch(r"[A-Z]{2}", code):
        raise ValueError("a two-letter country code, like US")
    return code


HttpUrlStr = Annotated[str, AfterValidator(_http_url)]
Ein = Annotated[str, AfterValidator(_ein)]
CountryCode = Annotated[str, AfterValidator(_country)]


class OrganizationCreate(BaseModel):
    orgId: UUID
    orgName: str
    orgEmail: str
    orgDisabled: bool
    # defaults to America/New_York when omitted
    orgTimezone: IanaTimezone | None = None


class OrganizationOut(BaseModel):
    orgId: UUID | None = None
    orgName: str | None = None

    orgCreatedAt: datetime | None = None
    orgEmail: str | None = None
    orgDisabled: bool | None = None
    orgTimezone: str | None = None
    # business profile (BE-07)
    orgAddress: str | None = None
    orgPhone: str | None = None
    orgEin: str | None = None
    orgCountry: str | None = None
    orgLogoUrl: str | None = None
    orgSocials: dict[str, str] = {}
    orgWebsites: list[str] = []

    model_config = ConfigDict(from_attributes=True)


class OrganizationUpdate(BaseModel):
    orgName: str | None = None
    orgEmail: str | None = None
    orgDisabled: bool | None = None
    orgTimezone: IanaTimezone | None = None
    # business profile (BE-07): leaving a field out keeps it; null clears it,
    # except the lists, where {} / [] clear them
    orgAddress: str | None = None
    orgPhone: str | None = None
    orgEin: Ein | None = None
    orgCountry: CountryCode | None = None
    orgLogoUrl: HttpUrlStr | None = None
    # network name -> profile URL, e.g. {"instagram": "https://instagram.com/..."}
    orgSocials: dict[str, HttpUrlStr] | None = None
    orgWebsites: list[HttpUrlStr] | None = None

    @field_validator("orgSocials", "orgWebsites")
    @classmethod
    def _lists_cant_be_null(cls, value, info):
        if value is None:
            raise ValueError(f"{info.field_name} can't be null; send an empty one to clear it")
        return value
