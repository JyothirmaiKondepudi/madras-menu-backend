from pydantic import BaseModel, ConfigDict, Field, field_validator
from uuid import UUID
from typing import Literal


class UserOut(BaseModel):
    userId: UUID
    fullName: str
    userEmail: str
    userPhoneNumber: str | None = None
    preferredContact: str | None = None
    userDisabled: bool
    userAddress: str | None = None
    userRole: Literal["client", "vendor", "platform_admin"]
    userOrg: UUID

    model_config = ConfigDict(from_attributes=True)


def _normalize_email(value: str | None) -> str | None:
    # emails are case-insensitive, so store one spelling: otherwise
    # Jane@x.com and jane@x.com become two accounts that log in as each other
    return value.strip().lower() if value is not None else value


class UserCreate(BaseModel):
    fullName: str
    email: str
    phoneNumber: str | None = None
    preferredContact: Literal["email", "phone"] | None = None
    address: str | None = None
    role: Literal["client", "vendor", "platform_admin"]
    # Optional: lets whoever creates a user (a vendor, via this endpoint)
    # also set their login credential in the same call. A user created
    # without one just can't log in yet — not every user_data row needs to.
    # max_length matches bcrypt's own 72-byte input limit (silent truncation
    # past that, so this makes the limit visible instead of silent).
    password: str | None = Field(default=None, max_length=72)

    _email_lowercase = field_validator("email")(_normalize_email)


class UserUpdate(BaseModel):
    fullName: str | None = None
    email: str | None = None
    phoneNumber: str | None = None
    preferredContact: Literal["email", "phone"] | None = None
    address: str | None = None

    _email_lowercase = field_validator("email")(_normalize_email)
