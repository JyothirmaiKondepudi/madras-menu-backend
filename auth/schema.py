from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str
    password: str = Field(max_length=72)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ChangePasswordRequest(BaseModel):
    currentPassword: str = Field(max_length=72)
    newPassword: str = Field(min_length=8, max_length=72)
