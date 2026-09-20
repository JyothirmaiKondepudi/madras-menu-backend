from pydantic import BaseModel, ConfigDict, Field
from uuid import UUID

class UserOut(BaseModel):
    userId: UUID
    fullName: str
    userEmail: str
    userPhoneNumber: str
    preferredContact: str
    userAddress: str | None = None
    userRole:str
    hasNotification: bool = False

    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseModel):
    fullName: str
    email: str
    phoneNumber: str
    preferredContact: str
    address: str | None = None
    role: str
    # Optional: lets whoever creates a user (an admin, via this endpoint)
    # also set their login credential in the same call. A user created
    # without one just can't log in yet — not every user_data row needs to.
    # max_length matches bcrypt's own 72-byte input limit (silent truncation
    # past that, so this makes the limit visible instead of silent).
    password: str | None = Field(default=None, max_length=72)


class UserUpdate(BaseModel):
    fullName: str | None = None
    email: str | None = None
    phoneNumber: str | None = None
    preferredContact: str | None = None
    address: str | None = None
    role: str | None = None