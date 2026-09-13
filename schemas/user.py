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

    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseModel):
    fullName: str
    email: str
    phoneNumber: str
    preferredContact: str
    address: str | None = None
    role: str


class UserUpdate(BaseModel):
    fullName: str | None = None
    email: str | None = None
    phoneNumber: str | None = None
    preferredContact: str | None = None
    address: str | None = None
    role: str | None = None