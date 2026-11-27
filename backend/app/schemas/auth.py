import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,24}$")


class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)

    @field_validator("username")
    @classmethod
    def _username(cls, v: str) -> str:
        v = v.strip()
        if not USERNAME_RE.match(v):
            raise ValueError("Use 3–24 letters, numbers or underscores.")
        return v

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return v.strip().lower()


class LoginRequest(BaseModel):
    identifier: str = Field(min_length=1, max_length=254, description="Email or username")
    password: str = Field(min_length=1, max_length=128)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    email: str
    avatar_url: str | None
    created_at: datetime


class AuthResponse(BaseModel):
    user: UserResponse
